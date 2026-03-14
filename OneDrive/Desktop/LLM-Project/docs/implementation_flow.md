# ContractIQ Implementation Flow

## End-to-End Pipeline

1. User uploads contract (PDF/DOCX).
2. Ingestion layer extracts raw text.
3. Feed text into Mode 1 extraction prompt.
4. For each extracted clause, run RAG retrieval against playbook vector DB.
5. Feed clause + playbook rule + runtime context into Mode 2 analysis prompt.
6. For HIGH/CRITICAL or MUST CHANGE clauses, run Mode 3 redline prompt.
7. Feed outputs from Modes 1-3 into Mode 4 report prompt.
8. Render UI output:
   - Side-by-side clause + redline view
   - Downloadable Word with tracked changes

## Runtime Variables to Inject

- `{contract_text}`: Full extracted text from document
- `{jurisdiction}`: Detected or user-specified governing law
- `{contract_type}`: Detected or user-specified (MSA, NDA, SaaS, etc.)
- `{counterparty_type}`: Customer / Vendor / Partner / Employee
- `{playbook_rules}`: Retrieved from vector DB via RAG
- `{stance}`: AGGRESSIVE / BALANCED / CONSERVATIVE
- `{audience}`: Legal Counsel / Business Executive / Procurement Team
- `{full_analysis_json}`: Compiled output from Modes 1-3

## Recommended Orchestration Pattern

- Use one orchestrator function with deterministic stage outputs.
- Validate strict JSON after each mode before progressing.
- Persist intermediate artifacts:
  - `extraction.json`
  - `analysis.json`
  - `redlines.json`
  - `report.md`
- Fail closed: if parsing fails, stop and request rerun with repair prompt.

## Validation Gates

- Gate 1: Governing law must be detected or explicitly flagged unknown.
- Gate 2: Every extracted clause must have `clause_id` and `clause_type`.
- Gate 3: Every analyzed clause must include both legal and business risk.
- Gate 4: Every redline must include legal justification.
- Gate 5: Report must include legal disclaimer verbatim.

## Mandatory Closing Statement

Every review output should end with this sentence:

This output requires review by a qualified attorney before execution.
