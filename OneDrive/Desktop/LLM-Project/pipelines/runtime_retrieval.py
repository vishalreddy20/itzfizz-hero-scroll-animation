from __future__ import annotations

import json

from integrations.clients import get_chroma_client, get_embedder, get_ollama
from integrations.config import OLLAMA_MODEL
from integrations.exact_prompts import PLAYBOOK_RETRIEVAL_PROMPT
from integrations.prompt_utils import render_prompt
from integrations.schemas import PlaybookRetrievalResult
from integrations.validation import run_json_step_with_retries


def retrieve_playbook_rule(clause_text: str) -> dict:
    pb_collection = get_chroma_client().get_or_create_collection("playbook")
    query_embed = get_embedder().encode(clause_text).tolist()

    results = pb_collection.query(
        query_embeddings=[query_embed],
        n_results=3,
        include=["documents", "metadatas"],
    )

    retrieved = []
    for i, doc in enumerate(results["documents"][0]):
        retrieved.append(
            {
                "rank": i + 1,
                "text": doc,
                "metadata": results["metadatas"][0][i],
            }
        )

    prompt = render_prompt(
        PLAYBOOK_RETRIEVAL_PROMPT,
        clause_text=clause_text,
        retrieved_rules=json.dumps(retrieved, indent=2),
    )

    def call() -> str:
        return get_ollama().chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1},
        )["message"]["content"]

    return run_json_step_with_retries(call, PlaybookRetrievalResult, attempts=2).model_dump()
