from __future__ import annotations

import argparse
import json
from pathlib import Path

import pdfplumber

from docx import Document

from app.services.orchestrator import run_full_review
from integrations.clients import get_chroma_client, get_embedder, get_gemini_model, get_ollama
from integrations.config import OLLAMA_MODEL
from integrations.exact_prompts import PLAYBOOK_RETRIEVAL_PROMPT
from integrations.json_utils import parse_llm_json
from pipelines.groq_analysis import analyze_with_groq


def extract_text(file_path: str) -> str:
    if file_path.endswith(".pdf"):
        with pdfplumber.open(file_path) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
        return "\n".join(pages)

    if file_path.endswith(".docx"):
        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)

    if file_path.endswith(".txt"):
        return Path(file_path).read_text(encoding="utf-8")

    raise ValueError("Unsupported file extension. Use .pdf, .docx, or .txt")


def get_playbook_rule(clause_text: str) -> dict:
    collection = get_chroma_client().get_or_create_collection("playbook")
    embed = get_embedder().encode(clause_text).tolist()

    results = collection.query(
        query_embeddings=[embed],
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

    prompt = PLAYBOOK_RETRIEVAL_PROMPT.format(
        clause_text=clause_text,
        retrieved_rules=json.dumps(retrieved, indent=2),
    )

    response = get_ollama().chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    selected = parse_llm_json(response["message"]["content"])

    if selected.get("no_playbook_coverage"):
        return {"company_position": "No rule found — apply general standard"}

    return selected.get("best_matching_rule", {})


def generate_redline(clause: dict, analysis: dict) -> dict | None:
    if not analysis.get("redline_needed"):
        return None

    # Uses existing project redline service schema by simulating analysis input.
    return {
        "clause_id": clause.get("clause_id"),
        "clause_type": analysis.get("clause_type", clause.get("clause_type")),
        "issue_summary": analysis.get("deviation_from_playbook", ""),
        "analysis_summary": analysis,
    }


def generate_report(analysis_results: list[dict], redlines: list[dict]) -> str:
    model = get_gemini_model()
    prompt = (
        "Generate a concise executive report in JSON with keys summary, blockers, priorities "
        "from this analysis payload:\n"
        + json.dumps({"analysis": analysis_results, "redlines": redlines}, indent=2)
    )
    response = model.generate_content(prompt)
    return response.text


def run_contract_review(file_path: str, jurisdiction: str, contract_type: str) -> dict:
    print("Step 1: Extracting text...")
    text = extract_text(file_path)

    print("Step 2: Extracting clauses...")
    review = run_full_review(
        contract_text=text,
        jurisdiction=jurisdiction,
        contract_type=contract_type,
        counterparty_type="Vendor",
        stance="BALANCED",
        audience="Legal Counsel",
        playbook_path=Path("playbook/company_legal_playbook_v1.md"),
        output_dir=Path("output"),
    )
    clauses = review["extraction"]["clauses"]

    print("Step 3: Analyzing risks with Groq...")
    analysis_results: list[dict] = []
    redlines: list[dict] = []

    for clause in clauses:
        rule = get_playbook_rule(clause["original_text"])
        analysis = analyze_with_groq(
            clause_text=clause["original_text"],
            playbook_rule=rule,
            jurisdiction=jurisdiction,
            contract_type=contract_type,
            clause_id=clause["clause_id"],
        )
        analysis_results.append(analysis)
        maybe_redline = generate_redline(clause, analysis)
        if maybe_redline is not None:
            redlines.append(maybe_redline)

    print("Step 4: Generating report...")
    report = generate_report(analysis_results, redlines)

    output = {
        "clauses": clauses,
        "analysis": analysis_results,
        "redlines": redlines,
        "report": report,
    }

    Path("contract_review_output.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print("Done. Output saved to contract_review_output.json")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run free contract review pipeline")
    parser.add_argument("file_path", help="Path to contract file (.pdf/.docx/.txt)")
    parser.add_argument("--jurisdiction", default="Delaware")
    parser.add_argument("--contract_type", default="MSA")
    args = parser.parse_args()

    run_contract_review(args.file_path, args.jurisdiction, args.contract_type)
