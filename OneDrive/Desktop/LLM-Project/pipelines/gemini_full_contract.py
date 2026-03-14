from __future__ import annotations

import json

from integrations.clients import get_gemini_model
from integrations.exact_prompts import GEMINI_FULL_CONTRACT_PROMPT
from integrations.json_utils import parse_llm_json
from integrations.prompt_utils import render_prompt


def analyze_full_contract_gemini(full_contract_text: str) -> dict:
    prompt = render_prompt(GEMINI_FULL_CONTRACT_PROMPT, full_contract_text=full_contract_text)
    response = get_gemini_model().generate_content(prompt)
    return parse_llm_json(response.text)
