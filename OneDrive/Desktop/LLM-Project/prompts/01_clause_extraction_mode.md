PROMPT — CLAUSE EXTRACTION (MODE 1)

You are operating in EXTRACTION MODE.

INPUT: Raw contract text (provided below)
TASK: Extract every distinct clause and return structured JSON

INSTRUCTIONS:
1. Read the entire contract before extracting
2. Identify natural clause boundaries (by heading, number, or logical break)
3. Label each clause using the standard taxonomy (see system prompt)
4. If a clause does not match any taxonomy category, label it "CUSTOM: [your label]"
5. Preserve the EXACT original text — do not paraphrase
6. Note the approximate position (beginning / middle / end) if no page numbers exist
7. Flag any clause that appears MISSING from a standard contract of this type

OUTPUT FORMAT (strict JSON):
{
  "contract_metadata": {
    "contract_type": "",
    "parties": ["", ""],
    "effective_date": "",
    "governing_law": "",
    "total_clauses_found": 0,
    "missing_standard_clauses": []
  },
  "clauses": [
    {
      "clause_id": "C001",
      "clause_type": "",
      "heading": "",
      "original_text": "",
      "position": "",
      "word_count": 0,
      "contains_defined_terms": true,
      "cross_references": [],
      "extraction_confidence": "HIGH",
      "extraction_notes": ""
    }
  ]
}

CRITICAL RULES:
- Do NOT summarize original_text. Copy it exactly.
- Do NOT skip clauses even if they seem boilerplate.
- If a clause is embedded inside another clause, extract it as a sub-clause.
- Flag [AMBIGUOUS] if clause boundaries are unclear.

CONTRACT TEXT:
{contract_text}
