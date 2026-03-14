from __future__ import annotations

from typing import Any

import httpx
from datasets import load_dataset_builder

from integrations.dataset_catalog import DATASET_CATALOG


def get_dataset_catalog() -> list[dict[str, Any]]:
    return DATASET_CATALOG


def check_ollama_available() -> tuple[bool, str]:
    try:
        response = httpx.get("http://127.0.0.1:11434/api/tags", timeout=5.0)
        if response.status_code == 200:
            return True, "Ollama is reachable"
        return False, f"Ollama returned status {response.status_code}"
    except Exception as exc:
        return False, f"Ollama unavailable: {exc}"


def check_cuad_available() -> tuple[bool, str]:
    try:
        load_dataset_builder("cuad")
        return True, "CUAD builder resolved successfully"
    except Exception as exc:
        return False, f"CUAD unavailable: {exc}"


def get_dataset_processing_status() -> dict[str, Any]:
    ollama_ok, ollama_reason = check_ollama_available()
    cuad_ok, cuad_reason = check_cuad_available()
    return {
        "process_record_ready": ollama_ok,
        "process_record_reason": ollama_reason,
        "cuad_ingest_ready": cuad_ok,
        "cuad_ingest_reason": cuad_reason,
        "recommended_datasets": [
            {
                "key": item["key"],
                "name": item["name"],
                "purpose": item["purpose"],
                "primary_link": item["huggingface"] or item["direct_download"],
            }
            for item in DATASET_CATALOG
        ],
    }
