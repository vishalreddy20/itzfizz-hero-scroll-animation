from __future__ import annotations

import json

from integrations.clients import get_groq_client
from integrations.config import GROQ_MODEL
from integrations.exact_prompts import GROQ_ANALYSIS_PROMPT
from integrations.prompt_utils import render_prompt
from integrations.schemas import GroqAnalysisResult
from integrations.validation import run_json_step_with_retries


def analyze_with_groq(
    clause_text: str,
    playbook_rule: dict,
    jurisdiction: str,
    contract_type: str,
    clause_id: str,
) -> dict:
    def call() -> str:
        prompt = render_prompt(
            GROQ_ANALYSIS_PROMPT,
            clause_text=clause_text,
            playbook_rule=json.dumps(playbook_rule),
            jurisdiction=jurisdiction,
            contract_type=contract_type,
            clause_id=clause_id,
        )

        response = get_groq_client().chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a legal contract analysis AI. Return only valid JSON. No prose.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.1,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content

    return run_json_step_with_retries(call, GroqAnalysisResult, attempts=2).model_dump()
