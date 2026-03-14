from __future__ import annotations

import json


def parse_llm_json(raw: str) -> dict:
    clean = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(clean)
