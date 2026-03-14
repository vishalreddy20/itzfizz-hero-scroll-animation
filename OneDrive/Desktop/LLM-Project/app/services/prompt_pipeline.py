from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from app.services.analysis import analyze_clauses
from app.services.extraction import extract_clauses
from app.services.observability import estimate_cost_usd, estimate_tokens
from app.services.playbook import load_playbook
from app.services.redline import generate_redlines
from app.services.reporting import generate_report_markdown
from app.services.runtime_config import get_runtime_profile
from integrations.clients import get_gemini_model, get_ollama
from integrations.config import OLLAMA_MODEL
from integrations.exact_prompts import (
    EXACT_EXECUTIVE_REPORT_PROMPT,
    EXACT_REDLINE_PROMPT,
    PROMPT_PACK_VERSION,
    PROMPT_VERSIONS,
)
from integrations.prompt_utils import render_prompt
from integrations.schemas import RedlineResult
from integrations.validation import run_json_step_with_retries, validate_report_text
from pipelines.groq_analysis import analyze_with_groq
from pipelines.runtime_retrieval import retrieve_playbook_rule


def run_prompt_review(
    contract_text: str,
    jurisdiction: str,
    contract_type: str,
    counterparty_type: str,
    stance: str,
    audience: str,
    playbook_path: Path,
) -> dict[str, Any]:
    profile = get_runtime_profile()
    extraction = extract_clauses(contract_text)
    metadata = extraction["contract_metadata"]
    if contract_type and contract_type != "Unknown":
        metadata["contract_type"] = contract_type
    if jurisdiction and jurisdiction != "Unknown":
        metadata["governing_law"] = jurisdiction

    playbook_index = load_playbook(playbook_path)
    local_analysis = analyze_clauses(
        extraction=extraction,
        playbook_index=playbook_index,
        jurisdiction=metadata["governing_law"],
        contract_type=metadata["contract_type"],
        counterparty_type=counterparty_type,
    )
    local_redlines = generate_redlines(extraction=extraction, analysis=local_analysis, stance=stance)
    local_redline_map = {item["clause_id"]: item for item in local_redlines}

    analysis_items: list[dict[str, Any]] = []
    retrieved_rules: dict[str, dict[str, Any]] = {}
    fallback_reason = ""

    for clause in extraction["clauses"]:
        local_item = _find_local_item(local_analysis["analysis"], clause["clause_id"])
        try:
            retrieval = retrieve_playbook_rule(clause["original_text"])
            retrieved_rules[clause["clause_id"]] = retrieval
            analysis_result = analyze_with_groq(
                clause_text=clause["original_text"],
                playbook_rule=retrieval["best_matching_rule"],
                jurisdiction=metadata["governing_law"],
                contract_type=metadata["contract_type"],
                clause_id=clause["clause_id"],
            )
            analysis_items.append(_normalize_prompt_analysis(clause, retrieval, analysis_result, metadata["governing_law"]))
        except Exception:
            fallback_reason = "partial prompt fallback to local rule analysis"
            analysis_items.append(local_item)

    overall_risk = _overall_risk(analysis_items)
    analysis = {
        "analysis": analysis_items,
        "overall_contract_risk": overall_risk,
        "overall_risk_summary": _overall_summary(analysis_items, metadata["contract_type"]),
        "critical_blockers": [
            f"{item['clause_id']} {item['clause_type']}"
            for item in analysis_items
            if item["negotiation_priority"] == "MUST CHANGE" or item["legal_risk"] == "CRITICAL"
        ],
        "recommended_next_step": _next_step(overall_risk),
    }

    redlines: list[dict[str, Any]] = []
    for item in analysis_items:
        if item["legal_risk"] not in {"CRITICAL", "HIGH"} and item["negotiation_priority"] != "MUST CHANGE":
            continue
        clause = _find_clause(extraction["clauses"], item["clause_id"])
        retrieval = retrieved_rules.get(item["clause_id"], {})
        playbook_language = retrieval.get("best_matching_rule", {}).get("preferred_language", "")
        try:
            redlines.append(
                _generate_exact_redline(
                    clause=clause,
                    analysis_item=item,
                    playbook_language=playbook_language,
                )
            )
        except Exception:
            fallback_reason = "partial prompt fallback to local redlines"
            fallback = local_redline_map.get(item["clause_id"])
            if fallback:
                redlines.append(fallback)

    report_markdown = _generate_exact_report(
        extraction=extraction,
        analysis=analysis,
        redlines=redlines,
        audience=audience,
        fallback=lambda: generate_report_markdown(extraction, analysis, redlines, audience=audience),
    )

    return {
        "extraction": extraction,
        "analysis": analysis,
        "redlines": redlines,
        "report_markdown": report_markdown,
        "pipeline_mode_used": "prompt",
        "providers_used": ["ollama", "groq", "gemini"],
        "fallback_reason": fallback_reason,
        "prompt_version": {
            "pack": PROMPT_PACK_VERSION,
            "modules": PROMPT_VERSIONS,
        },
        "telemetry": {
            "contract_tokens_estimate": estimate_tokens(contract_text),
            "cost_estimate_usd": {
                "groq": estimate_cost_usd(estimate_tokens(contract_text), 0.0006),
                "gemini": estimate_cost_usd(estimate_tokens(contract_text), 0.0004),
                "ollama": 0.0,
            },
        },
    }


def _generate_exact_redline(
    clause: dict[str, Any],
    analysis_item: dict[str, Any],
    playbook_language: str,
) -> dict[str, Any]:
    profile = get_runtime_profile()
    prompt = render_prompt(
        EXACT_REDLINE_PROMPT,
        original_clause_text=clause["original_text"],
        risk_analysis=json.dumps(analysis_item, indent=2),
        playbook_language=playbook_language or "[NO PLAYBOOK LANGUAGE AVAILABLE]",
    )

    def call() -> str:
        return get_ollama().chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1},
        )["message"]["content"]

    validated = run_json_step_with_retries(call, RedlineResult, attempts=profile.retry_attempts)
    return validated.model_dump()


def _generate_exact_report(
    extraction: dict[str, Any],
    analysis: dict[str, Any],
    redlines: list[dict[str, Any]],
    audience: str,
    fallback: Callable[[], str],
) -> str:
    profile = get_runtime_profile()
    full_analysis_json = json.dumps(
        {
            "extraction": extraction,
            "analysis": analysis,
            "redlines": redlines,
        },
        indent=2,
    )
    prompt = render_prompt(
        EXACT_EXECUTIVE_REPORT_PROMPT,
        full_analysis_json=full_analysis_json,
        audience=audience,
    )
    for _ in range(profile.retry_attempts):
        try:
            response = get_gemini_model().generate_content(prompt)
            return validate_report_text(response.text)
        except Exception:
            try:
                response = get_ollama().chat(
                    model=OLLAMA_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    options={"temperature": 0.1},
                )
                return validate_report_text(response["message"]["content"])
            except Exception:
                continue
    return fallback()


def _normalize_prompt_analysis(
    clause: dict[str, Any],
    retrieval: dict[str, Any],
    analysis_result: dict[str, Any],
    jurisdiction: str,
) -> dict[str, Any]:
    confidence = analysis_result.get("confidence", "LOW")
    legal_risk = analysis_result["legal_risk"]
    human_review_reason = "Low model confidence." if confidence == "LOW" else ""
    if retrieval.get("no_playbook_coverage"):
        human_review_reason = "No direct playbook coverage." if not human_review_reason else f"{human_review_reason} No direct playbook coverage."

    return {
        "clause_id": analysis_result["clause_id"],
        "clause_type": analysis_result["clause_type"] or clause["clause_type"],
        "playbook_rule_applied": retrieval.get("best_matching_rule", {}).get("rule_id") or "[NO PLAYBOOK RULE]",
        "deviation_summary": analysis_result["deviation_from_playbook"],
        "legal_risk": legal_risk,
        "legal_risk_reasoning": analysis_result["legal_risk_reason"],
        "business_risk": analysis_result["business_risk"],
        "business_risk_reasoning": analysis_result["business_risk_reason"],
        "real_world_impact": analysis_result["real_world_impact"],
        "negotiation_priority": analysis_result["negotiation_priority"],
        "missing_protections": [],
        "favorable_elements": [],
        "unfavorable_elements": retrieval.get("best_matching_rule", {}).get("never_accept", []),
        "jurisdiction_specific_notes": f"Jurisdiction considered: {jurisdiction}.",
        "human_review_required": confidence == "LOW" or legal_risk in {"CRITICAL", "HIGH"},
        "human_review_reason": human_review_reason,
    }


def _find_local_item(items: list[dict[str, Any]], clause_id: str) -> dict[str, Any]:
    for item in items:
        if item["clause_id"] == clause_id:
            return item
    raise KeyError(f"Missing local analysis item for {clause_id}")


def _find_clause(clauses: list[dict[str, Any]], clause_id: str) -> dict[str, Any]:
    for clause in clauses:
        if clause["clause_id"] == clause_id:
            return clause
    raise KeyError(f"Missing clause {clause_id}")


def _overall_risk(items: list[dict[str, Any]]) -> str:
    levels = [item["legal_risk"] for item in items]
    for level in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        if level in levels:
            return level
    return "LOW"


def _overall_summary(items: list[dict[str, Any]], contract_type: str) -> str:
    overall = _overall_risk(items)
    must_change = sum(1 for item in items if item["negotiation_priority"] == "MUST CHANGE")
    return f"{contract_type} review identified overall {overall} risk with {must_change} MUST CHANGE items."


def _next_step(risk: str) -> str:
    if risk in {"CRITICAL", "HIGH"}:
        return "Escalate to legal counsel, negotiate blockers, and re-review before signature."
    return "Proceed with minor edits and attorney confirmation before execution."
