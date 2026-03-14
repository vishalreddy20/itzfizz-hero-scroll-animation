from __future__ import annotations

from typing import Any

from integrations.validation import REQUIRED_REPORT_DISCLAIMER, REQUIRED_REVIEW_CLOSING


FORBIDDEN_REPORT_PATTERNS = [
    "this is legal advice",
    "guaranteed to win",
    "certainly enforceable",
]


class GuardrailViolationError(ValueError):
    pass


def enforce_guardrails(review_result: dict[str, Any]) -> None:
    _validate_report(review_result.get("report_markdown", ""))
    _validate_redlines(review_result.get("redlines", []))


def _validate_report(report_markdown: str) -> None:
    text_lower = report_markdown.lower()
    for pattern in FORBIDDEN_REPORT_PATTERNS:
        if pattern in text_lower:
            raise GuardrailViolationError(f"Forbidden report phrase detected: {pattern}")

    if REQUIRED_REPORT_DISCLAIMER not in report_markdown:
        raise GuardrailViolationError("Report disclaimer missing from final report")
    if REQUIRED_REVIEW_CLOSING not in report_markdown:
        raise GuardrailViolationError("Attorney review closing line missing")


def _validate_redlines(redlines: list[dict[str, Any]]) -> None:
    for redline in redlines:
        if not redline.get("issue_summary"):
            raise GuardrailViolationError("Redline missing issue_summary")
        versions = redline.get("redline_versions") or {}
        for version_name in ["preferred", "fallback", "walk_away"]:
            version = versions.get(version_name) or {}
            if not version.get("legal_justification"):
                raise GuardrailViolationError(f"Redline {version_name} missing legal_justification")
