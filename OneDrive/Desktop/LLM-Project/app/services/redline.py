from __future__ import annotations

from typing import Any


def generate_redlines(
    extraction: dict[str, Any],
    analysis: dict[str, Any],
    stance: str,
) -> list[dict[str, Any]]:
    clause_map = {clause["clause_id"]: clause for clause in extraction["clauses"]}
    redlines: list[dict[str, Any]] = []

    for item in analysis["analysis"]:
        if item["legal_risk"] not in {"CRITICAL", "HIGH"} and item["negotiation_priority"] != "MUST CHANGE":
            continue

        clause = clause_map[item["clause_id"]]
        original = clause["original_text"]
        issue_summary = item["deviation_summary"] or "Clause requires negotiation adjustments."

        preferred = _build_version(original, item, "AGGRESSIVE")
        fallback = _build_version(original, item, "BALANCED")
        walk_away = _build_version(original, item, "CONSERVATIVE")

        redlines.append(
            {
                "clause_id": item["clause_id"],
                "clause_type": item["clause_type"],
                "original_text": original,
                "issue_summary": issue_summary,
                "redline_versions": {
                    "preferred": preferred,
                    "fallback": fallback,
                    "walk_away": walk_away,
                },
                "new_defined_terms_needed": _defined_terms_needed(item),
                "cross_clause_impacts": clause.get("cross_references", []),
                "attorney_note": f"Primary stance requested: {stance}. Validate consistency with remaining contract provisions.",
            }
        )

    return redlines


def _build_version(original: str, analysis_item: dict[str, Any], tone: str) -> dict[str, str]:
    insert_text = _suggest_insert(analysis_item, tone)
    return {
        "redlined_text": f"[STRIKETHROUGH: {original}] [INSERT: {insert_text}]",
        "change_summary": _change_summary(analysis_item),
        "legal_justification": _legal_justification(analysis_item),
        "tone": tone,
    }


def _suggest_insert(item: dict[str, Any], tone: str) -> str:
    clause_type = item["clause_type"].lower()

    if "limitation of liability" in clause_type:
        if tone == "AGGRESSIVE":
            return "Each party's aggregate liability shall not exceed the greater of twelve (12) months of fees paid or the total fees payable under this Agreement, provided that liability for fraud, willful misconduct, and IP infringement remains uncapped."
        if tone == "BALANCED":
            return "Each party's aggregate liability shall not exceed fees paid in the twelve (12) months preceding the claim, excluding fraud, willful misconduct, and third-party IP infringement obligations."
        return "Each party's aggregate liability shall be capped at fees paid under this Agreement in the twelve (12) months preceding the claim."

    if "indemnification" in clause_type:
        if tone == "AGGRESSIVE":
            return "The parties shall mutually indemnify, defend, and hold harmless each other from third-party claims arising from IP infringement, gross negligence, or willful misconduct."
        if tone == "BALANCED":
            return "Each party will indemnify the other for third-party claims to the extent caused by such party's IP infringement or gross negligence."
        return "Indemnification shall be mutual and limited to third-party claims directly attributable to the indemnifying party's acts or omissions."

    if "data privacy" in clause_type:
        if tone == "AGGRESSIVE":
            return "The parties shall execute a DPA, provide breach notice within seventy-two (72) hours, and delete personal data within thirty (30) days after termination unless retention is legally required."
        if tone == "BALANCED":
            return "The parties shall maintain commercially reasonable privacy safeguards, implement a DPA where required, and provide prompt breach notice."
        return "Each party shall comply with applicable data protection laws and cooperate in executing a DPA if personal data is processed."

    return "The parties agree to revise this clause to align with mutual obligations, clear risk allocation, and applicable law."


def _change_summary(item: dict[str, Any]) -> str:
    return f"Adjusts {item['clause_type']} to reduce identified {item['legal_risk']} legal risk."


def _legal_justification(item: dict[str, Any]) -> str:
    return "Revision narrows overbroad exposure, aligns rights and obligations, and improves enforceability and allocation of liability."


def _defined_terms_needed(item: dict[str, Any]) -> list[str]:
    text = " ".join(item.get("missing_protections", []))
    terms: list[str] = []
    if "DPA" in text:
        terms.append("Data Processing Addendum")
    if "liability cap" in text.lower():
        terms.append("Liability Cap")
    return terms
