from __future__ import annotations

from integrations.clients import get_ollama
from integrations.config import OLLAMA_MODEL
from integrations.exact_prompts import DATASET_PROCESSING_PROMPT
from integrations.prompt_utils import render_prompt
from integrations.schemas import DatasetProcessingResult
from integrations.validation import run_json_step_with_retries


def process_dataset_record(dataset_record: str) -> dict:
    prompt = render_prompt(DATASET_PROCESSING_PROMPT, dataset_record=dataset_record)

    def call() -> str:
        return get_ollama().chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1},
        )["message"]["content"]

    return run_json_step_with_retries(call, DatasetProcessingResult, attempts=2).model_dump()
