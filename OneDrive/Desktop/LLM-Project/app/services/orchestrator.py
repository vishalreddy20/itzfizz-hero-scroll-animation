from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from app.services.analysis import analyze_clauses
from app.services.extraction import extract_clauses
from app.services.guardrails import enforce_guardrails
from app.services.observability import finish_span_ms, start_span, write_audit_event
from app.services.playbook import load_playbook
from app.services.prompt_pipeline import run_prompt_review
from app.services.runtime_config import get_runtime_profile
from app.services.redline import generate_redlines
from app.services.reporting import generate_report_markdown
from integrations.exact_prompts import PROMPT_PACK_VERSION, PROMPT_VERSIONS


def run_full_review(
    contract_text: str,
    jurisdiction: str,
    contract_type: str,
    counterparty_type: str,
    stance: str,
    audience: str,
    playbook_path: Path,
    output_dir: Path,
    pipeline_mode: str = "auto",
) -> dict[str, Any]:
    span = start_span()
    request_id = str(uuid.uuid4())
    profile = get_runtime_profile()

    if pipeline_mode not in {"auto", "local", "prompt"}:
        raise ValueError("pipeline_mode must be one of: auto, local, prompt")

    fallback_reason = ""
    effective_mode = pipeline_mode
    if pipeline_mode == "auto":
        effective_mode = profile.preferred_pipeline_mode

    if effective_mode == "prompt":
        result = run_prompt_review(
            contract_text=contract_text,
            jurisdiction=jurisdiction,
            contract_type=contract_type,
            counterparty_type=counterparty_type,
            stance=stance,
            audience=audience,
            playbook_path=playbook_path,
        )
    elif effective_mode == "local":
        result = _run_local_review(
            contract_text=contract_text,
            jurisdiction=jurisdiction,
            contract_type=contract_type,
            counterparty_type=counterparty_type,
            stance=stance,
            audience=audience,
            playbook_path=playbook_path,
        )
    else:
        try:
            result = run_prompt_review(
                contract_text=contract_text,
                jurisdiction=jurisdiction,
                contract_type=contract_type,
                counterparty_type=counterparty_type,
                stance=stance,
                audience=audience,
                playbook_path=playbook_path,
            )
        except Exception as exc:
            fallback_reason = f"prompt pipeline failed: {exc}"
            result = _run_local_review(
                contract_text=contract_text,
                jurisdiction=jurisdiction,
                contract_type=contract_type,
                counterparty_type=counterparty_type,
                stance=stance,
                audience=audience,
                playbook_path=playbook_path,
            )

    result.setdefault("providers_used", ["local-rules"])
    result.setdefault("fallback_reason", fallback_reason)
    result.setdefault(
        "prompt_version",
        {
            "pack": PROMPT_PACK_VERSION,
            "modules": PROMPT_VERSIONS,
        },
    )

    enforce_guardrails(result)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "extraction.json", result["extraction"])
    _write_json(output_dir / "analysis.json", result["analysis"])
    _write_json(output_dir / "redlines.json", {"redlines": result["redlines"]})
    _write_json(
        output_dir / "metadata.json",
        {
            "request_id": request_id,
            "created_at_unix": time.time(),
            "profile": profile.name,
            "pipeline_mode_requested": pipeline_mode,
            "pipeline_mode_used": result.get("pipeline_mode_used", effective_mode),
            "providers_used": result.get("providers_used", []),
            "fallback_reason": result.get("fallback_reason", ""),
            "prompt_version": result.get("prompt_version", {}),
            "telemetry": result.get("telemetry", {}),
        },
    )
    _write_json(
        output_dir / "contract_review_output.json",
        {
            "request_id": request_id,
            "pipeline_mode_used": result.get("pipeline_mode_used", effective_mode),
            "providers_used": result.get("providers_used", []),
            "prompt_version": result.get("prompt_version", {}),
            "extraction": result["extraction"],
            "analysis": result["analysis"],
            "redlines": result["redlines"],
            "report_markdown": result["report_markdown"],
        },
    )
    (output_dir / "report.md").write_text(result["report_markdown"], encoding="utf-8")

    duration_ms = finish_span_ms(span)
    write_audit_event(
        output_dir=output_dir,
        event_type="review_completed",
        payload={
            "request_id": request_id,
            "profile": profile.name,
            "pipeline_mode_requested": pipeline_mode,
            "pipeline_mode_used": result.get("pipeline_mode_used", effective_mode),
            "providers_used": result.get("providers_used", []),
            "fallback_reason": result.get("fallback_reason", ""),
            "duration_ms": duration_ms,
            "token_estimate": result.get("telemetry", {}).get("contract_tokens_estimate", 0),
            "cost_estimate_usd": result.get("telemetry", {}).get("cost_estimate_usd", {}),
        },
    )

    result["request_id"] = request_id
    return result


def _run_local_review(
    contract_text: str,
    jurisdiction: str,
    contract_type: str,
    counterparty_type: str,
    stance: str,
    audience: str,
    playbook_path: Path,
) -> dict[str, Any]:
    playbook_index = load_playbook(playbook_path)
    extraction = extract_clauses(contract_text)

    if contract_type and contract_type != "Unknown":
        extraction["contract_metadata"]["contract_type"] = contract_type
    if jurisdiction and jurisdiction != "Unknown":
        extraction["contract_metadata"]["governing_law"] = jurisdiction

    analysis = analyze_clauses(
        extraction=extraction,
        playbook_index=playbook_index,
        jurisdiction=extraction["contract_metadata"]["governing_law"],
        contract_type=extraction["contract_metadata"]["contract_type"],
        counterparty_type=counterparty_type,
    )
    redlines = generate_redlines(extraction=extraction, analysis=analysis, stance=stance)
    report_markdown = generate_report_markdown(extraction, analysis, redlines, audience=audience)

    return {
        "extraction": extraction,
        "analysis": analysis,
        "redlines": redlines,
        "report_markdown": report_markdown,
        "pipeline_mode_used": "local",
        "providers_used": ["local-rules"],
        "fallback_reason": "",
        "prompt_version": {
            "pack": PROMPT_PACK_VERSION,
            "modules": PROMPT_VERSIONS,
        },
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
