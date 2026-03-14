from __future__ import annotations

import hashlib
import json
from pathlib import Path
from threading import Lock
from typing import Any


class IdempotencyStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = Lock()

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            return self._read().get(key)

    def set(self, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            payload = self._read()
            payload[key] = value
            self._write(payload)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
