from __future__ import annotations

from typing import Any

from app.services.legal_ml import predict_clause_risk
from app.services.playbook import PlaybookIndex


RISK_SEVERITY = {
    "COMPLIANT": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


def analyze_clauses(
    extraction: dict[str, Any],
    playbook_index: PlaybookIndex,
    jurisdiction: str,
    contract_type: str,
    counterparty_type: str,
) -> dict[str, Any]:
    analyses: list[dict[str, Any]] = []

    for clause in extraction["clauses"]:
        original_text = clause["original_text"]
        clause_type = clause["clause_type"]
        rule = playbook_index.lookup(f"{clause_type}\n{original_text}")

        playbook_rule_applied = rule.clause_name if rule else "[NO PLAYBOOK RULE]"
        deviation_summary, missing, favorable, unfavorable = _deviation_summary(clause, rule)
        legal_risk, legal_reason = _legal_risk(clause, rule, counterparty_type)
        model_prediction = predict_clause_risk(clause_type, original_text)
        legal_risk, legal_reason, risk_source = _merge_with_model_signal(legal_risk, legal_reason, model_prediction)
        business_risk, business_reason = _business_risk(clause, legal_risk)
        priority = _negotiation_priority(legal_risk, business_risk)

        review_reason = "" if "[AMBIGUOUS]" not in clause.get("extraction_notes", "") else "Clause boundary ambiguous."
        human_review_required = legal_risk in {"CRITICAL", "HIGH"} or bool(review_reason)

        analyses.append(
            {
                "clause_id": clause["clause_id"],
                "clause_type": clause_type,
                "playbook_rule_applied": playbook_rule_applied,
                "deviation_summary": deviation_summary,
                "legal_risk": legal_risk,
                "legal_risk_reasoning": legal_reason,
                "risk_source": risk_source,
                "model_risk_prediction": model_prediction.label if model_prediction else "",
                "model_risk_confidence": round(model_prediction.confidence, 3) if model_prediction else 0.0,
                "business_risk": business_risk,
                "business_risk_reasoning": business_reason,
                "real_world_impact": _real_world_impact(clause_type, legal_risk),
                "negotiation_priority": priority,
                "missing_protections": missing,
                "favorable_elements": favorable,
                "unfavorable_elements": unfavorable,
                "jurisdiction_specific_notes": _jurisdiction_notes(jurisdiction, clause_type),
                "human_review_required": human_review_required,
                "human_review_reason": review_reason,
            }
        )

    overall_contract_risk = _overall_risk(analyses)
    blockers = [
        f"{a['clause_id']} {a['clause_type']}"
        for a in analyses
        if a["negotiation_priority"] == "MUST CHANGE" or a["legal_risk"] == "CRITICAL"
    ]

    return {
        "analysis": analyses,
        "overall_contract_risk": overall_contract_risk,
        "overall_risk_summary": _overall_summary(overall_contract_risk, analyses, contract_type),
        "critical_blockers": blockers,
        "recommended_next_step": _next_step(overall_contract_risk),
    }


def _deviation_summary(clause: dict[str, Any], rule: Any) -> tuple[str, list[str], list[str], list[str]]:
    text = clause["original_text"].lower()
    missing: list[str] = []
    favorable: list[str] = []
    unfavorable: list[str] = []

    if "limitation of liability" in clause["clause_type"].lower() or "liability" in text:
        if "unlimited" in text or "without limit" in text:
            unfavorable.append("Potential uncapped liability exposure.")
        if "cap" not in text and "limit" not in text:
            missing.append("No explicit liability cap detected.")
        if "indirect" in text or "consequential" in text:
            favorable.append("Includes exclusion language for indirect or consequential damages.")

    if "indemn" in text:
        if "mutual" in text:
            favorable.append("Mutual indemnification appears to be present.")
        else:
            unfavorable.append("Indemnification may be unilateral.")

    if "data" in text and "breach" not in text:
        missing.append("No breach notification timing found.")

    if not rule:
        return ("[NO PLAYBOOK RULE] Clause reviewed under general legal standards.", missing, favorable, unfavorable)

    summary = "Compared against playbook clause guidance; deviations identified in risk vectors."
    return (summary, missing, favorable, unfavorable)


def _legal_risk(clause: dict[str, Any], rule: Any, counterparty_type: str) -> tuple[str, str]:
    text = clause["original_text"].lower()
    clause_type = clause["clause_type"].lower()

    if "unlimited" in text and "liability" in text:
        return ("CRITICAL", "Clause exposes potentially uncapped liability." )

    if "indemn" in clause_type or "indemn" in text:
        if "sole" in text or "exclusive" in text and "indemn" in text:
            return ("HIGH", "Indemnification language appears one-sided or overly broad.")

    if "data privacy" in clause_type or "gdpr" in text or "ccpa" in text:
        if "dpa" not in text and "data processing" not in text:
            return ("CRITICAL", "Data processing obligations appear incomplete without DPA framework.")

    if "governing law" in clause_type and "unknown" in text:
        return ("MEDIUM", "Governing law clause lacks clarity.")

    if not rule:
        return ("MEDIUM", "No direct playbook rule matched; requires manual legal validation.")

    if "termination" in clause_type and "convenience" in text and "30" not in text:
        return ("HIGH", "Termination rights may not include balanced notice and payment protections.")

    if counterparty_type.lower() == "vendor" and "assignment" in clause_type and "consent" in text:
        return ("LOW", "Assignment appears constrained but manageable.")

    return ("COMPLIANT", "Clause is generally aligned with playbook expectations.")


def _merge_with_model_signal(legal_risk: str, legal_reason: str, model_prediction: Any) -> tuple[str, str, str]:
    if model_prediction is None:
        return (legal_risk, legal_reason, "rules")

    predicted = str(model_prediction.label)
    confidence = float(model_prediction.confidence)
    predicted_severity = RISK_SEVERITY.get(predicted, 0)
    current_severity = RISK_SEVERITY.get(legal_risk, 0)

    if predicted_severity > current_severity:
        return (
            predicted,
            f"{legal_reason} ML classifier escalated this clause to {predicted} risk ({confidence:.2f} confidence).",
            "rules+ml",
        )

    return (
        legal_risk,
        f"{legal_reason} ML classifier observed {predicted} risk ({confidence:.2f} confidence) but rule-based risk remained controlling.",
        "rules+ml",
    )


def _business_risk(clause: dict[str, Any], legal_risk: str) -> tuple[str, str]:
    clause_type = clause["clause_type"]
    if legal_risk == "CRITICAL":
        return ("CRITICAL", "High legal exposure could materially disrupt commercial operations.")
    if legal_risk == "HIGH":
        return ("HIGH", "Term may affect pricing, support obligations, or negotiation leverage.")
    if legal_risk == "MEDIUM":
        return ("MEDIUM", "Clause is negotiable but may create process or cost friction.")

    if "Notice" in clause_type or "Severability" in clause_type:
        return ("LOW", "Administrative clause with low operational impact.")
    return ("NEUTRAL", "No material business impact identified.")


def _real_world_impact(clause_type: str, legal_risk: str) -> str:
    if legal_risk == "CRITICAL":
        return "If executed as-is, this term could create uncapped exposure, regulatory penalties, or material financial loss."
    if legal_risk == "HIGH":
        return "If unchanged, this term may increase claim risk and weaken leverage in disputes."
    if legal_risk == "MEDIUM":
        return "If accepted without edits, this term can introduce avoidable cost and operational friction over the contract lifecycle."
    return "This term is unlikely to create significant legal or operational harm in its current form."


def _jurisdiction_notes(jurisdiction: str, clause_type: str) -> str:
    if "Governing Law" in clause_type and jurisdiction.lower() in {"unknown", ""}:
        return "[AMBIGUOUS] Governing law not reliably detected; legal review required."
    return f"Jurisdiction considered: {jurisdiction}."


def _negotiation_priority(legal_risk: str, business_risk: str) -> str:
    if legal_risk == "CRITICAL" or business_risk == "CRITICAL":
        return "MUST CHANGE"
    if legal_risk == "HIGH" or business_risk == "HIGH":
        return "SHOULD CHANGE"
    if legal_risk == "MEDIUM" or business_risk == "MEDIUM":
        return "NICE TO HAVE"
    return "ACCEPT"


def _overall_risk(analyses: list[dict[str, Any]]) -> str:
    levels = [item["legal_risk"] for item in analyses]
    if "CRITICAL" in levels:
        return "CRITICAL"
    if "HIGH" in levels:
        return "HIGH"
    if "MEDIUM" in levels:
        return "MEDIUM"
    if "LOW" in levels:
        return "LOW"
    return "LOW"


def _overall_summary(risk: str, analyses: list[dict[str, Any]], contract_type: str) -> str:
    must_change = sum(1 for item in analyses if item["negotiation_priority"] == "MUST CHANGE")
    return f"{contract_type} review identified overall {risk} risk with {must_change} MUST CHANGE items."


def _next_step(risk: str) -> str:
    if risk in {"CRITICAL", "HIGH"}:
        return "Escalate to legal counsel, negotiate blockers, and re-review before signature."
    return "Proceed with minor edits and attorney confirmation before execution."
