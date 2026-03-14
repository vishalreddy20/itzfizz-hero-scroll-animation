# ContractIQ - Functional Contract Review App

This repository now includes a fully runnable end-to-end application with:

- Contract upload and text ingestion (`.txt`, `.pdf`, `.docx`)
- Clause extraction and classification (Mode 1)
- Playbook lookup and risk analysis (Mode 2)
- Redline generation for high-risk terms (Mode 3)
- Executive report generation (Mode 4)
- Browser UI and JSON/Markdown artifacts in `output/`
- API key auth + per-client rate limiting (profile-based)
- Async job processing for heavy review/ingestion workflows
- Audit log telemetry (`output/audit_log.jsonl`)
- Redis-backed distributed rate limiter and job status store (optional)
- OpenTelemetry tracing/metrics export (OTLP, Jaeger-compatible OTLP, Prometheus)
- Tamper-evident signed audit hash-chain for compliance validation
- Prompt/versioned output metadata for reproducibility
- Idempotent ingestion endpoints (content-hash dedup)

## Project Structure

- `app/main.py` - FastAPI server and endpoints
- `app/services/` - Ingestion, extraction, analysis, redline, reporting orchestration
- `app/static/` - Frontend UI
- `playbook/company_legal_playbook_v1.md` - Retrieval source
- `prompts/` - Prompt pack files
- `sample/sample_contract.txt` - Sample contract input
- `output/` - Generated artifacts (`extraction.json`, `analysis.json`, `redlines.json`, `report.md`)

## Run Locally (PowerShell)

```powershell
cd c:\Users\reddy\OneDrive\Desktop\LLM-Project
./run.ps1
```

Or run manually:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open in browser:

`http://127.0.0.1:8000`

## API Endpoints

- `GET /api/health`
- `GET /api/ready`
- `POST /api/review` (JSON body with `contract_text`)
- `POST /api/review-async` (returns `job_id`)
- `POST /api/review-file` (multipart upload + runtime fields)
- `GET /api/jobs/{job_id}` (poll async status)
- `POST /api/ingest/playbook`
- `POST /api/process-dataset-record`
- `POST /api/ingest/cuad` (queued background job)

All protected endpoints support `X-API-Key` when required by active profile.

## Local Model Training

ContractIQ ships a trainable legal-risk clause classifier that integrates into every review automatically once a model artifact is present.

### Datasets

| Dataset | Source | Size | Used For |
|---|---|---|---|
| **CUAD** | `cuad` (HF Hub) | 13K+ QA pairs · 41 clause categories | Clause extraction & risk mapping |
| **LEDGAR** | `lex_glue` / ledgar | 60K SEC provisions · 100 classes | Provision type → risk classification |
| **ContractNLI** | `kiddothe2b/contract-nli` | 17K NDA NLI triples | NDA clause compliance risk |
| Seed data | `training/seed_legal_risk_dataset.jsonl` | 30 hand-crafted examples | Quick local baseline |
| MultiLexSum | `allenai/multi_lexsum` | — | Summarization RAG *(future)* |
| Law-StackExchange | `ymoslem/Law-StackExchange` | — | Legal Q&A RAG *(future)* |

### Step 1 — Download & convert the public datasets

```powershell
# All three datasets (≤ 5 000 rows each — adjust with --limit)
python -m training.ingest_datasets

# Specific datasets only
python -m training.ingest_datasets --datasets cuad,contractnli

# No row limit (downloads everything — can be large)
python -m training.ingest_datasets --limit 0
```

Outputs written to `training/`:
- `training/cuad_dataset.jsonl`
- `training/ledgar_dataset.jsonl`
- `training/contractnli_dataset.jsonl`

### Step 2 — Train the model

**Option A — TF-IDF (fast, no GPU, good baseline):**
```powershell
python -m training.train_legal_risk_model `
    --dataset-path training/seed_legal_risk_dataset.jsonl `
    --dataset-path training/cuad_dataset.jsonl `
    --dataset-path training/ledgar_dataset.jsonl `
    --dataset-path training/contractnli_dataset.jsonl `
    --backend tfidf
```

**Option B — Legal-BERT (best accuracy, downloads ~440 MB on first run):**
```powershell
python -m training.train_legal_risk_model `
    --dataset-path training/seed_legal_risk_dataset.jsonl `
    --dataset-path training/cuad_dataset.jsonl `
    --dataset-path training/ledgar_dataset.jsonl `
    --dataset-path training/contractnli_dataset.jsonl `
    --backend legal-bert `
    --sentence-model-name nlpaueb/legal-bert-base-uncased
```

**Option C — Sentence-Transformer bi-encoder:**
```powershell
python -m training.train_legal_risk_model `
    --dataset-path training/cuad_dataset.jsonl `
    --backend sentence-transformer `
    --sentence-model-name all-MiniLM-L6-v2
```

Artifacts written to `models/` (gitignored):
- `models/legal_risk_model.joblib`
- `models/legal_risk_model_metrics.json`

### Step 3 — The model activates automatically

Once `models/legal_risk_model.joblib` exists, every clause in every review call gets a model signal. Per-clause response fields added:

```json
{
  "risk_source": "rules+ml",
  "model_risk_prediction": "CRITICAL",
  "model_risk_confidence": 0.72
}
```

Control via `.env`:

```env
CONTRACTIQ_LEGAL_MODEL_ENABLED=true
CONTRACTIQ_LEGAL_MODEL_PATH=./models/legal_risk_model.joblib
CONTRACTIQ_LEGAL_MODEL_MIN_CONFIDENCE=0.35
```

### Legal-BERT model

The `legal-bert` backend uses [`nlpaueb/legal-bert-base-uncased`](https://huggingface.co/nlpaueb/legal-bert-base-uncased) — a BERT model pre-trained on 12 GB of diverse English legal text (EU legislation, ECJ case law, UK legislation, US contracts, US court cases). This produces substantially better embeddings for contract clause risk classification than a general-purpose bi-encoder.

## Runtime Profiles

- `local-dev`: local deterministic mode preferred, no API key required
- `api-fast`: prompt mode preferred, auth required, higher throughput
- `api-accurate`: prompt mode preferred, auth required, stricter retry policy

Configure in `.env`:

```powershell
CONTRACTIQ_PROFILE=local-dev
CONTRACTIQ_API_KEYS=my-dev-key-1,my-dev-key-2
```

## Async Workflows

1. Submit review job using `POST /api/review-async`
2. Poll `GET /api/jobs/{job_id}` until status is `completed` or `failed`
3. Read final result from `result` field

`POST /api/ingest/cuad` also runs in background and returns a `job_id`.

## Observability and Audit

- Per-request audit events are stored at `output/audit_log.jsonl`
- Review metadata is stored at `output/metadata.json`
- Full reproducible bundle is stored at `output/contract_review_output.json`
- Audit entries include `previous_hash`, `event_hash`, and `event_signature_hmac_sha256`
- Chain tip is tracked in `output/audit_chain_state.json`

## Redis Distributed State

Enable Redis-backed limiter + job store:

```powershell
CONTRACTIQ_REDIS_ENABLED=true
CONTRACTIQ_REDIS_URL=redis://localhost:6379/0
```

When disabled or unavailable, the app gracefully falls back to in-memory behavior.

## OpenTelemetry Export

Enable telemetry:

```powershell
CONTRACTIQ_OTEL_ENABLED=true
CONTRACTIQ_OTEL_SERVICE_NAME=contractiq-api
CONTRACTIQ_OTEL_EXPORTER=otlp
CONTRACTIQ_OTEL_OTLP_ENDPOINT=http://localhost:4318/v1/traces
```

Exporter options:

- `otlp`: OTLP HTTP exporter (works with OTLP collectors and Jaeger OTLP ingest)
- `jaeger`: alias behavior to OTLP endpoint for Jaeger-compatible collector paths
- `prometheus`: Prometheus metrics endpoint on `CONTRACTIQ_OTEL_PROMETHEUS_PORT`
- `console`: local debug spans to console

## Dataset and API Integration (Exact Prompt System)

Integrated modules:

- `integrations/exact_prompts.py`
- `integrations/config.py`
- `integrations/clients.py`
- `pipelines/dataset_record_process.py`
- `pipelines/cuad_ingest.py`
- `pipelines/playbook_ingest.py`
- `pipelines/runtime_retrieval.py`
- `pipelines/groq_analysis.py`
- `pipelines/gemini_full_contract.py`
- `pipelines/master_free_pipeline.py`

Set environment variables:

```powershell
Copy-Item .env.example .env
```

Then fill:

- `GROQ_API_KEY`
- `GEMINI_API_KEY`
- Optional: `HF_TOKEN`

Run playbook ingestion:

```powershell
c:/Users/reddy/OneDrive/Desktop/LLM-Project/.venv/Scripts/python.exe -m pipelines.playbook_ingest --input playbook/company_legal_playbook_v1.md
```

Run CUAD ingestion (first 500 by default):

```powershell
c:/Users/reddy/OneDrive/Desktop/LLM-Project/.venv/Scripts/python.exe -m pipelines.cuad_ingest --limit 500
```

Run complete free pipeline on a contract:

```powershell
c:/Users/reddy/OneDrive/Desktop/LLM-Project/.venv/Scripts/python.exe -m pipelines.master_free_pipeline sample/sample_contract.txt --jurisdiction Delaware --contract_type MSA
```

This writes `contract_review_output.json` in the project root.

If `chromadb` is not installed or cannot compile on the local machine, the project automatically falls back to a local JSON vector store under `CHROMA_PATH` with cosine retrieval.

## Notes

- Outputs are deterministic and generated from rule-based logic plus playbook retrieval.
- Local ML-assisted clause risk scoring is supported once a legal risk model is trained.
- Artifacts are saved on every review run into `output/`.

## Security Hardening

- Upload security includes max-size enforcement, signature checks, and parser error hard-fail
- Guardrails enforce required legal disclaimer and redline legal-justification integrity
- Rate limiter protects endpoints from runaway traffic

## Deployment

Build container:

```powershell
docker build -t contractiq .
docker run --rm -p 8000:8000 --env-file .env contractiq
```

CI workflow is included at `.github/workflows/ci.yml`.

## Safety Notice

This system supports legal workflow acceleration and does not replace legal counsel.
All outputs should be reviewed by qualified attorneys.
