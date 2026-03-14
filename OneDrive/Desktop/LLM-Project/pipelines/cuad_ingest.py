from __future__ import annotations

import argparse
from typing import Any

from datasets import load_dataset

from integrations.clients import get_chroma_client, get_embedder, get_ollama
from integrations.config import OLLAMA_MODEL
from integrations.exact_prompts import CUAD_PROCESSING_PROMPT
from integrations.prompt_utils import render_prompt
from integrations.validation import parse_and_validate


class CuadProcessingResult(dict):
    pass


def process_cuad_record(record: dict[str, Any]) -> dict[str, Any] | None:
    oll = get_ollama()
    answer = "NONE"
    if record.get("answers") and record["answers"].get("text"):
        answer_list = record["answers"]["text"]
        if answer_list:
            answer = answer_list[0]

    prompt = render_prompt(
        CUAD_PROCESSING_PROMPT,
        context=(record.get("context") or "")[:3000],
        question=record.get("question") or "",
        answer=answer,
    )

    response = oll.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.1},
    )
    raw = response["message"]["content"]

    try:
        payload = parse_and_validate(raw, _CuadRecordSchema)
        return payload.model_dump()
    except Exception:
        return None


def embed_and_store(processed: dict[str, Any] | None, record_id: int) -> None:
    if not processed or not processed.get("use_for_rag"):
        return

    text = processed["extracted_text"]
    embedder = get_embedder()
    chroma = get_chroma_client()
    collection = chroma.get_or_create_collection("cuad_clauses")
    embedding = embedder.encode(text).tolist()

    collection.add(
        documents=[text],
        embeddings=[embedding],
        metadatas=[
            {
                "clause_type": processed.get("clause_type", ""),
                "quality": processed.get("quality", "LOW"),
                "source": "CUAD",
            }
        ],
        ids=[f"cuad_{record_id}"],
    )


def run(limit: int) -> None:
    print("Loading CUAD dataset...")
    try:
        cuad = load_dataset("cuad", split="train")
    except Exception as exc:
        raise RuntimeError(
            "CUAD could not be loaded from Hugging Face in this environment. "
            "Try https://huggingface.co/datasets/cuad or direct download at "
            "https://zenodo.org/record/4599830"
        ) from exc

    print("Processing CUAD records...")
    for i, record in enumerate(cuad):
        if i >= limit:
            break
        processed = process_cuad_record(record)
        embed_and_store(processed, i)
        if i % 50 == 0:
            print(f"Processed {i} records...")

    print("CUAD dataset loaded into ChromaDB successfully.")


from pydantic import BaseModel


class _CuadRecordSchema(BaseModel):
    clause_type: str
    extracted_text: str
    context_window: str
    quality: str
    use_for_rag: bool
    reason_if_rejected: str


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest CUAD records into ChromaDB")
    parser.add_argument("--limit", type=int, default=500, help="Number of CUAD records to process")
    args = parser.parse_args()
    run(args.limit)
