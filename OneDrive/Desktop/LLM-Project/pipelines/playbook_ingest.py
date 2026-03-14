from __future__ import annotations

import argparse
import json
from pathlib import Path

from integrations.clients import get_chroma_client, get_embedder, get_ollama
from integrations.config import OLLAMA_MODEL
from integrations.exact_prompts import PLAYBOOK_INGESTION_PROMPT
from integrations.prompt_utils import render_prompt
from integrations.schemas import PlaybookIngestionResult
from integrations.validation import run_json_step_with_retries


def ingest_playbook(raw_text: str) -> dict:
    prompt = render_prompt(PLAYBOOK_INGESTION_PROMPT, raw_playbook_text=raw_text)

    def call() -> str:
        return get_ollama().chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1},
        )["message"]["content"]

    payload = run_json_step_with_retries(call, PlaybookIngestionResult, attempts=2).model_dump()

    chroma = get_chroma_client()
    embedder = get_embedder()
    pb_collection = chroma.get_or_create_collection("playbook")

    for rule in payload.get("playbook_rules", []):
        text = f"{rule.get('clause_type', '')}: {rule.get('company_position', '')} {rule.get('preferred_language', '')}"
        embedding = embedder.encode(text).tolist()
        pb_collection.add(
            documents=[rule.get("preferred_language", "")],
            embeddings=[embedding],
            metadatas=[rule],
            ids=[rule.get("rule_id", "")],
        )

    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest playbook into ChromaDB")
    parser.add_argument(
        "--input",
        default="playbook/company_legal_playbook_v1.md",
        help="Path to raw playbook text",
    )
    args = parser.parse_args()

    raw = Path(args.input).read_text(encoding="utf-8")
    result = ingest_playbook(raw)
    print(json.dumps({"stored_rules": len(result.get("playbook_rules", []))}, indent=2))
