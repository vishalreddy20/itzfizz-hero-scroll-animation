from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.models import (
    AsyncJobResponse,
    CuadIngestionRequest,
    DatasetRecordRequest,
    GenericPayloadResponse,
    HealthResponse,
    JobStatusResponse,
    PlaybookIngestionRequest,
    ReadinessResponse,
    ReviewRequest,
    ReviewResponse,
)
from app.services.idempotency import IdempotencyStore, content_hash
from app.services.dataset_health import get_dataset_catalog, get_dataset_processing_status
from app.services.jobs import JOB_MANAGER
from app.services.observability import write_audit_event
from app.services.redis_backend import get_redis_client
from app.services.runtime_config import is_otel_enabled, is_redis_enabled, validate_environment
from app.services.security import SecurityContext, enforce_security
from app.services.telemetry import configure_telemetry
from app.services.ingestion import extract_text_from_upload
from app.services.orchestrator import run_full_review
from pipelines.cuad_ingest import run as ingest_cuad
from pipelines.dataset_record_process import process_dataset_record
from pipelines.playbook_ingest import ingest_playbook

ROOT_DIR = Path(__file__).resolve().parents[1]
PLAYBOOK_PATH = ROOT_DIR / "playbook" / "company_legal_playbook_v1.md"
OUTPUT_DIR = ROOT_DIR / "output"
STATIC_DIR = ROOT_DIR / "app" / "static"
IDEMPOTENCY_STORE = IdempotencyStore(OUTPUT_DIR / "idempotency_store.json")

app = FastAPI(title="ContractIQ", version="1.0.0")
configure_telemetry(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=FileResponse)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/ready", response_model=ReadinessResponse)
def readiness(_security: SecurityContext = Depends(enforce_security)) -> ReadinessResponse:
    env = validate_environment()
    redis_ok = get_redis_client() is not None if is_redis_enabled() else True
    details = str(env["reason"])
    if not redis_ok:
        details = "Redis enabled but unavailable"
    if is_otel_enabled():
        details = f"{details}; otel_enabled=true"
    return ReadinessResponse(
        status="ready" if bool(env["ready"]) and redis_ok else "not-ready",
        profile=str(env["profile"]),
        reason=details,
    )


@app.get("/api/datasets/catalog", response_model=GenericPayloadResponse)
def dataset_catalog(_security: SecurityContext = Depends(enforce_security)) -> GenericPayloadResponse:
    return GenericPayloadResponse(payload={"datasets": get_dataset_catalog()})


@app.get("/api/datasets/status", response_model=GenericPayloadResponse)
def dataset_status(_security: SecurityContext = Depends(enforce_security)) -> GenericPayloadResponse:
    return GenericPayloadResponse(payload=get_dataset_processing_status())


@app.post("/api/review", response_model=ReviewResponse)
def review(request: ReviewRequest, http_request: Request, security: SecurityContext = Depends(enforce_security)) -> ReviewResponse:
    try:
        result = run_full_review(
            contract_text=request.contract_text,
            jurisdiction=request.jurisdiction,
            contract_type=request.contract_type,
            counterparty_type=request.counterparty_type,
            stance=request.stance,
            audience=request.audience,
            playbook_path=PLAYBOOK_PATH,
            output_dir=OUTPUT_DIR,
            pipeline_mode=request.pipeline_mode,
        )
        write_audit_event(
            output_dir=OUTPUT_DIR,
            event_type="api_review",
            payload={
                "path": str(http_request.url.path),
                "request_id": result.get("request_id", ""),
                "client_id": security.client_id,
                "pipeline_mode": request.pipeline_mode,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ReviewResponse(**result)


@app.post("/api/review-async", response_model=AsyncJobResponse)
def review_async(request: ReviewRequest, _security: SecurityContext = Depends(enforce_security)) -> AsyncJobResponse:
    job_id = JOB_MANAGER.submit(
        "review",
        task=lambda: run_full_review(
            contract_text=request.contract_text,
            jurisdiction=request.jurisdiction,
            contract_type=request.contract_type,
            counterparty_type=request.counterparty_type,
            stance=request.stance,
            audience=request.audience,
            playbook_path=PLAYBOOK_PATH,
            output_dir=OUTPUT_DIR,
            pipeline_mode=request.pipeline_mode,
        ),
    )
    return AsyncJobResponse(job_id=job_id, status="queued")


@app.post("/api/review-file", response_model=ReviewResponse)
async def review_file(
    contract_file: UploadFile = File(...),
    jurisdiction: str = Form("Unknown"),
    contract_type: str = Form("Unknown"),
    counterparty_type: str = Form("Vendor"),
    stance: str = Form("BALANCED"),
    audience: str = Form("Legal Counsel"),
    pipeline_mode: str = Form("auto"),
    security: SecurityContext = Depends(enforce_security),
) -> ReviewResponse:
    try:
        content = await contract_file.read()
        contract_text = extract_text_from_upload(contract_file.filename or "uploaded.txt", content)
        result = run_full_review(
            contract_text=contract_text,
            jurisdiction=jurisdiction,
            contract_type=contract_type,
            counterparty_type=counterparty_type,
            stance=stance,
            audience=audience,
            playbook_path=PLAYBOOK_PATH,
            output_dir=OUTPUT_DIR,
            pipeline_mode=pipeline_mode,
        )
        write_audit_event(
            output_dir=OUTPUT_DIR,
            event_type="api_review_file",
            payload={
                "request_id": result.get("request_id", ""),
                "client_id": security.client_id,
                "filename": contract_file.filename or "",
                "pipeline_mode": pipeline_mode,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ReviewResponse(**result)


@app.post("/api/ingest/playbook", response_model=GenericPayloadResponse)
def ingest_playbook_endpoint(request: PlaybookIngestionRequest, _security: SecurityContext = Depends(enforce_security)) -> GenericPayloadResponse:
    payload_hash = content_hash(request.raw_text)
    cached = IDEMPOTENCY_STORE.get(payload_hash)
    if cached:
        return GenericPayloadResponse(payload={"idempotent": True, **cached.get("payload", {})})

    try:
        payload = ingest_playbook(request.raw_text)
        IDEMPOTENCY_STORE.set(payload_hash, {"payload": payload})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GenericPayloadResponse(payload=payload)


@app.post("/api/process-dataset-record", response_model=GenericPayloadResponse)
def process_dataset_record_endpoint(request: DatasetRecordRequest, _security: SecurityContext = Depends(enforce_security)) -> GenericPayloadResponse:
    payload_hash = content_hash(request.dataset_record)
    cached = IDEMPOTENCY_STORE.get(payload_hash)
    if cached:
        return GenericPayloadResponse(payload={"idempotent": True, **cached.get("payload", {})})

    try:
        payload = process_dataset_record(request.dataset_record)
        IDEMPOTENCY_STORE.set(payload_hash, {"payload": payload})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GenericPayloadResponse(payload=payload)


@app.post("/api/ingest/cuad", response_model=GenericPayloadResponse)
def ingest_cuad_endpoint(request: CuadIngestionRequest, _security: SecurityContext = Depends(enforce_security)) -> GenericPayloadResponse:
    job_id = JOB_MANAGER.submit(
        "cuad_ingestion",
        task=lambda: _run_cuad_job(request.limit),
    )
    return GenericPayloadResponse(payload={"status": "queued", "job_id": job_id, "records_requested": request.limit})


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str, _security: SecurityContext = Depends(enforce_security)) -> JobStatusResponse:
    record = JOB_MANAGER.get(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        job_id=record.job_id,
        job_type=record.job_type,
        status=record.status,
        result=record.result,
        error=record.error,
    )


def _run_cuad_job(limit: int) -> dict[str, int | str]:
    ingest_cuad(limit)
    return {"status": "ok", "records_ingested": limit}
