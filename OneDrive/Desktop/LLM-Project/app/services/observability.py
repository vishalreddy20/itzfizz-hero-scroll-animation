from __future__ import annotations

import json
import hashlib
import hmac
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from app.services.runtime_config import get_audit_signing_secret


_AUDIT_LOCK = Lock()


@dataclass
class TimedSpan:
    start: float


def start_span() -> TimedSpan:
    return TimedSpan(start=time.perf_counter())


def finish_span_ms(span: TimedSpan) -> float:
    return round((time.perf_counter() - span.start) * 1000, 2)


def estimate_tokens(text: str) -> int:
    # Approximation for telemetry, not billing grade.
    return max(1, len(text) // 4)


def estimate_cost_usd(token_count: int, usd_per_1k_tokens: float) -> float:
    return round((token_count / 1000.0) * usd_per_1k_tokens, 6)


def write_audit_event(output_dir: Path, event_type: str, payload: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "audit_log.jsonl"
    state_path = output_dir / "audit_chain_state.json"

    previous_hash = ""
    if state_path.exists():
        try:
            previous_hash = json.loads(state_path.read_text(encoding="utf-8")).get("last_hash", "")
        except Exception:
            previous_hash = ""

    row = {
        "event_type": event_type,
        "timestamp_unix": time.time(),
        **payload,
    }

    material = json.dumps({"previous_hash": previous_hash, "row": row}, ensure_ascii=True, sort_keys=True)
    event_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()
    signature = hmac.new(
        get_audit_signing_secret().encode("utf-8"),
        event_hash.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    row["previous_hash"] = previous_hash
    row["event_hash"] = event_hash
    row["event_signature_hmac_sha256"] = signature

    with _AUDIT_LOCK:
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=True) + "\n")
        state_path.write_text(json.dumps({"last_hash": event_hash}, ensure_ascii=True), encoding="utf-8")
