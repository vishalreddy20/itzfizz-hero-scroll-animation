"""training/ingest_datasets.py

Download and convert public legal datasets from HuggingFace Hub into the
ContractIQ training JSONL format:

    {"text": "...", "label": "CRITICAL|HIGH|MEDIUM|LOW|COMPLIANT",
     "clause_type": "...", "source": "<dataset_name>"}

Supported datasets:
  cuad          - CUAD v1.0  (Contract Understanding Atticus Dataset)
                  510 contracts · 41 clause categories · 13K+ QA pairs
  ledgar        - LEDGAR via lex_glue
                  60K SEC Act provisions · 100 provision classes
  contractnli   - ContractNLI  (kiddothe2b/contract-nli)
                  17K NDA NLI triples · 17 hypothesis types

Purpose-notes for datasets NOT used here for risk classification:
  multilexsum   - allenai/multi_lexsum  (better for summarization RAG)
  lawstackexchange - ymoslem/Law-StackExchange  (better for legal Q&A RAG)

Usage:
  # Ingest all three datasets (default limit 5 000 rows each)
  python -m training.ingest_datasets

  # Pick specific datasets
  python -m training.ingest_datasets --datasets cuad,contractnli

  # Raise the per-dataset row ceiling  (0 = no limit)
  python -m training.ingest_datasets --limit 10000

  # Custom output directory  (default: same training/ folder)
  python -m training.ingest_datasets --output-dir training/

Then train the model on the collected data:
  python -m training.train_legal_risk_model \\
      --dataset-path training/cuad_dataset.jsonl \\
      --dataset-path training/ledgar_dataset.jsonl \\
      --dataset-path training/contractnli_dataset.jsonl \\
      --backend legal-bert
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent  # training/


# ─────────────────────────────────────────────────────────────────────────────
#  CUAD  question-category → (risk_label, clause_type)
#  Ordered by specificity; first substring match wins.
# ─────────────────────────────────────────────────────────────────────────────
CUAD_CATEGORY_RISK: list[tuple[str, str, str]] = [
    # CRITICAL ─────────────────────────────────────────────────────────────
    ("Unlimited/No-Cap On Liability",    "CRITICAL",  "Limitation of Liability"),
    ("Uncapped Liability",               "CRITICAL",  "Limitation of Liability"),
    # HIGH ──────────────────────────────────────────────────────────────────
    ("Liquidated Damages",               "HIGH",      "Indemnification"),
    ("IP Ownership Assignment",          "HIGH",      "Intellectual Property"),
    ("Non-Compete",                      "HIGH",      "Non-Compete"),
    ("Exclusivity",                      "HIGH",      "Exclusivity"),
    ("Change Of Control",                "HIGH",      "Change of Control"),
    ("Termination For Convenience",      "HIGH",      "Term & Termination"),
    ("Irrevocable Or Perpetual License", "HIGH",      "License Grant"),
    ("Revenue/Profit Sharing",           "HIGH",      "Payment Terms & Invoicing"),
    # MEDIUM ────────────────────────────────────────────────────────────────
    ("Joint IP Ownership",               "MEDIUM",    "Intellectual Property"),
    ("Anti-Assignment",                  "MEDIUM",    "Assignment & Subcontracting"),
    ("No-Solicit Of Customers",          "MEDIUM",    "Non-Solicitation"),
    ("No-Solicit Of Employees",          "MEDIUM",    "Non-Solicitation"),
    ("Price Restrictions",               "MEDIUM",    "Payment Terms & Invoicing"),
    ("Volume Restriction",               "MEDIUM",    "Payment Terms & Invoicing"),
    ("Non-Transferable License",         "MEDIUM",    "License Grant"),
    ("ROFR/ROFO/ROFN",                   "MEDIUM",    "Rights of First Refusal"),
    ("Third Party Beneficiary",          "MEDIUM",    "Third Party Rights"),
    ("Competitive Restriction Exception","MEDIUM",    "Non-Compete"),
    ("Minimum Commitment",               "MEDIUM",    "Payment Terms & Invoicing"),
    ("Most Favored Nation",              "MEDIUM",    "Pricing Terms"),
    # LOW ───────────────────────────────────────────────────────────────────
    ("Non-Disparagement",                "LOW",       "Non-Disparagement"),
    ("Cap On Liability",                 "LOW",       "Limitation of Liability"),
    ("Liability Is Capped At",           "LOW",       "Limitation of Liability"),
    ("Audit Rights",                     "LOW",       "Audit Rights"),
    ("Insurance",                        "LOW",       "Insurance Requirements"),
    ("Notice Period To Terminate",       "LOW",       "Term & Termination"),
    ("Renewal Term",                     "LOW",       "Term & Termination"),
    ("Expiration Date",                  "LOW",       "Term & Termination"),
    ("Post-Termination Services",        "LOW",       "Term & Termination"),
    ("Source Code Escrow",               "LOW",       "Source Code Escrow"),
    ("Covenant Not To Sue",              "LOW",       "Indemnification"),
    ("Affiliate License",                "LOW",       "License Grant"),
    ("Warranty Duration",                "LOW",       "Warranty & Disclaimer"),
    # COMPLIANT ─────────────────────────────────────────────────────────────
    ("Governing Law",                    "COMPLIANT", "Governing Law & Jurisdiction"),
    ("License Grant",                    "COMPLIANT", "License Grant"),
]


def _extract_cuad_category(question: str) -> str | None:
    """Extract the clause category from a CUAD question string.

    CUAD questions look like:
      "Highlight the parts (if any) of this contract related to
       'Non-Compete' that should be reviewed by a lawyer. ..."
    """
    match = re.search(r"'([^']+)'", question)
    return match.group(1).strip() if match else None


def _map_cuad_category(category: str) -> tuple[str, str] | None:
    """Return (risk_label, clause_type) for a CUAD category, or None."""
    cat_lower = category.lower()
    for keyword, risk, clause_type in CUAD_CATEGORY_RISK:
        if keyword.lower() in cat_lower:
            return risk, clause_type
    return None


def _load_cuad_split() -> Any:
    try:
        from datasets import load_dataset  # type: ignore
    except ImportError as exc:
        raise RuntimeError("'datasets' package is not installed.") from exc

    load_attempts = [
        ("cuad", {}, "CUAD"),
        ("theatticusproject/cuad-qa", {"trust_remote_code": True}, "theatticusproject/cuad-qa"),
    ]
    last_error: Exception | None = None
    for dataset_name, kwargs, _display_name in load_attempts:
        try:
            return load_dataset(dataset_name, split="train", **kwargs)
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"CUAD failed to load from known sources: {last_error}")


def _ingest_cuad(limit: int, output_path: Path) -> int:
    """Download CUAD and convert to ContractIQ training JSONL."""
    print("  Downloading CUAD from HuggingFace Hub (may take a minute) ...")
    try:
        ds = _load_cuad_split()
    except Exception as exc:
        print(f"  [SKIP] CUAD failed to load: {exc}")
        return 0

    rows: list[dict[str, Any]] = []
    for record in ds:
        if limit and len(rows) >= limit:
            break

        question = str(record.get("question", ""))
        answers = record.get("answers") or {}
        answer_texts: list[str] = (
            answers.get("text", []) if isinstance(answers, dict) else []
        )

        # Only include records where the clause is actually present in the contract
        if not answer_texts:
            continue

        category = _extract_cuad_category(question)
        if not category:
            continue

        mapping = _map_cuad_category(category)
        if not mapping:
            continue

        risk_label, clause_type = mapping
        text = str(answer_texts[0]).strip()
        if len(text) < 20:
            continue

        rows.append({
            "text": text,
            "label": risk_label,
            "clause_type": clause_type,
            "source": "CUAD",
        })

    output_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows),
        encoding="utf-8",
    )
    return len(rows)


# ─────────────────────────────────────────────────────────────────────────────
#  LEDGAR  provision label → (risk_label, clause_type)
#  Matched case-insensitively as substring of the label name.
# ─────────────────────────────────────────────────────────────────────────────
LEDGAR_LABEL_RISK: list[tuple[str, str, str]] = [
    # CRITICAL ─────────────────────────────────────────────────────────────
    ("uncapped",              "CRITICAL",  "Limitation of Liability"),
    ("unlimited liability",   "CRITICAL",  "Limitation of Liability"),
    # HIGH ──────────────────────────────────────────────────────────────────
    ("indemnif",              "HIGH",      "Indemnification"),
    ("limitation of liab",    "HIGH",      "Limitation of Liability"),
    ("non-compet",            "HIGH",      "Non-Compete"),
    ("non compet",            "HIGH",      "Non-Compete"),
    ("exclusiv",              "HIGH",      "Exclusivity"),
    ("change of control",     "HIGH",      "Change of Control"),
    ("intellectual prop",     "HIGH",      "Intellectual Property"),
    ("ip right",              "HIGH",      "Intellectual Property"),
    ("liquidated damage",     "HIGH",      "Indemnification"),
    # MEDIUM ────────────────────────────────────────────────────────────────
    ("warrant",               "MEDIUM",    "Warranty & Disclaimer"),
    ("terminat",              "MEDIUM",    "Term & Termination"),
    ("assignment",            "MEDIUM",    "Assignment & Subcontracting"),
    ("confidential",          "MEDIUM",    "Confidentiality & NDA"),
    ("data protect",          "MEDIUM",    "Data Privacy & Security (GDPR / CCPA)"),
    ("privacy",               "MEDIUM",    "Data Privacy & Security (GDPR / CCPA)"),
    ("non-solicit",           "MEDIUM",    "Non-Solicitation"),
    ("force majeure",         "MEDIUM",    "Force Majeure"),
    ("dispute",               "MEDIUM",    "Dispute Resolution"),
    ("arbitration",           "MEDIUM",    "Dispute Resolution"),
    ("amendment",             "MEDIUM",    "Amendments"),
    # LOW ───────────────────────────────────────────────────────────────────
    ("audit",                 "LOW",       "Audit Rights"),
    ("insurance",             "LOW",       "Insurance Requirements"),
    ("notice",                "LOW",       "Notice Requirements"),
    ("payment",               "LOW",       "Payment Terms & Invoicing"),
    ("fee",                   "LOW",       "Payment Terms & Invoicing"),
    # COMPLIANT ─────────────────────────────────────────────────────────────
    ("governing law",         "COMPLIANT", "Governing Law & Jurisdiction"),
    ("entire agreement",      "COMPLIANT", "Entire Agreement"),
    ("severability",          "COMPLIANT", "Miscellaneous"),
    ("counterpart",           "COMPLIANT", "Miscellaneous"),
    ("definition",            "COMPLIANT", "Definitions"),
    ("recital",               "COMPLIANT", "Recitals"),
]


def _map_ledgar_label(label_name: str) -> tuple[str, str] | None:
    """Return (risk_label, clause_type) for a LEDGAR provision label, or None."""
    label_lower = label_name.lower()
    for keyword, risk, clause_type in LEDGAR_LABEL_RISK:
        if keyword in label_lower:
            return risk, clause_type
    return None


def _ingest_ledgar(limit: int, output_path: Path) -> int:
    """Download LEDGAR (via lex_glue) and convert to ContractIQ training JSONL."""
    try:
        from datasets import load_dataset  # type: ignore
    except ImportError:
        print("  [SKIP] 'datasets' package is not installed.")
        return 0

    print("  Downloading LEDGAR (lex_glue) from HuggingFace Hub ...")
    try:
        ds = load_dataset("lex_glue", "ledgar", split="train", trust_remote_code=True)
        label_names: list[str] = ds.features["label"].names
    except Exception as exc:
        print(f"  [SKIP] LEDGAR failed to load: {exc}")
        return 0

    rows: list[dict[str, Any]] = []
    for record in ds:
        if limit and len(rows) >= limit:
            break

        label_idx = int(record.get("label", -1))
        if label_idx < 0 or label_idx >= len(label_names):
            continue

        label_name = label_names[label_idx]
        mapping = _map_ledgar_label(label_name)
        if not mapping:
            continue

        risk_label, clause_type = mapping
        text = str(record.get("text", "")).strip()
        if len(text) < 20:
            continue

        rows.append({
            "text": text,
            "label": risk_label,
            "clause_type": clause_type,
            "source": "LEDGAR",
        })

    output_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows),
        encoding="utf-8",
    )
    return len(rows)


# ─────────────────────────────────────────────────────────────────────────────
#  ContractNLI  hypothesis × NLI label → (risk_label, clause_type)
#
#  For each hypothesis keyword:
#    invert=False  →  Entailment=base_risk, Neutral=MEDIUM, Contradiction=LOW
#    invert=True   →  Contradiction=base_risk, Neutral=MEDIUM, Entailment=LOW
#                     (used when the hypothesis describes a *protective* clause:
#                      contradicting it means the protection is absent → high risk)
# ─────────────────────────────────────────────────────────────────────────────
_ContractNLIEntry = tuple[str, str, str, bool]

CONTRACTNLI_HYPOTHESIS_MAP: list[_ContractNLIEntry] = [
    # (keyword, base_risk, clause_type, invert_on_contradiction)
    ("non-compete",             "HIGH",     "Non-Compete",                              False),
    ("non compete",             "HIGH",     "Non-Compete",                              False),
    ("solicitation",            "MEDIUM",   "Non-Solicitation",                         False),
    ("solicit",                 "MEDIUM",   "Non-Solicitation",                         False),
    ("reverse engineer",        "HIGH",     "Intellectual Property",                    False),
    ("residual",                "MEDIUM",   "Intellectual Property",                    False),
    ("competitor",              "HIGH",     "Non-Compete",                              False),
    ("unlimited",               "HIGH",     "Confidentiality & NDA",                    False),
    ("perpetual",               "HIGH",     "Confidentiality & NDA",                    False),
    # Protective clauses: absence (contradiction) = high risk
    ("return",                  "HIGH",     "Data Privacy & Security (GDPR / CCPA)",    True),
    ("delete",                  "HIGH",     "Data Privacy & Security (GDPR / CCPA)",    True),
    ("confidentiality",         "MEDIUM",   "Confidentiality & NDA",                    True),
    ("inform",                  "MEDIUM",   "Notice Requirements",                      True),
    ("notice of breach",        "HIGH",     "Confidentiality & NDA",                    True),
    # Neutral clause patterns
    ("third part",              "MEDIUM",   "Third Party Rights",                       False),
    ("government",              "MEDIUM",   "Regulatory Compliance",                    False),
    ("share",                   "MEDIUM",   "Data Privacy & Security (GDPR / CCPA)",   False),
    ("amendment",               "LOW",      "Amendments",                               False),
    ("integration",             "LOW",      "Entire Agreement",                         False),
]


def _nli_label_to_str(label: Any) -> str:
    """Normalise a ContractNLI label (int or str) to 'entailment'/'neutral'/'contradiction'."""
    if isinstance(label, int):
        mapping = {0: "entailment", 1: "neutral", 2: "contradiction"}
        return mapping.get(label, "neutral")
    s = str(label).lower().strip()
    for canonical in ("entailment", "contradiction", "neutral"):
        if canonical in s:
            return canonical
    return "neutral"


def _map_contractnli(hypothesis: str, nli_label_str: str) -> tuple[str, str] | None:
    """Return (risk_label, clause_type) by matching hypothesis content and NLI label."""
    hyp_lower = hypothesis.lower()
    for keyword, base_risk, clause_type, invert in CONTRACTNLI_HYPOTHESIS_MAP:
        if keyword.lower() not in hyp_lower:
            continue
        if invert:
            if nli_label_str == "contradiction":
                return base_risk, clause_type
            if nli_label_str == "entailment":
                return "LOW", clause_type
            return "MEDIUM", clause_type
        else:
            if nli_label_str == "entailment":
                return base_risk, clause_type
            if nli_label_str == "neutral":
                return "MEDIUM", clause_type
            return "LOW", clause_type
    return None


def _ingest_contractnli(limit: int, output_path: Path) -> int:
    """Download ContractNLI and convert to ContractIQ training JSONL."""
    try:
        from datasets import load_dataset  # type: ignore
    except ImportError:
        print("  [SKIP] 'datasets' package is not installed.")
        return 0

    print("  Downloading ContractNLI from HuggingFace Hub ...")
    try:
        datasets_to_merge = [
            load_dataset("kiddothe2b/contract-nli", "contractnli_a", split="train", trust_remote_code=True),
            load_dataset("kiddothe2b/contract-nli", "contractnli_b", split="train", trust_remote_code=True),
        ]
    except Exception as exc:
        print(f"  [SKIP] ContractNLI failed to load: {exc}")
        return 0

    rows: list[dict[str, Any]] = []
    for ds in datasets_to_merge:
        for record in ds:
            if limit and len(rows) >= limit:
                break

            text = str(
                record.get("premise") or record.get("context") or record.get("text", "")
            ).strip()
            hypothesis = str(record.get("hypothesis", "")).strip()
            raw_label = record.get("label", 1)

            if len(text) < 20 or not hypothesis:
                continue

            nli_str = _nli_label_to_str(raw_label)
            mapping = _map_contractnli(hypothesis, nli_str)
            if not mapping:
                continue

            risk_label, clause_type = mapping
            rows.append({
                "text": text,
                "label": risk_label,
                "clause_type": clause_type,
                "source": "ContractNLI",
            })
        if limit and len(rows) >= limit:
            break

    output_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows),
        encoding="utf-8",
    )
    return len(rows)


# ─────────────────────────────────────────────────────────────────────────────
#  Registry + CLI
# ─────────────────────────────────────────────────────────────────────────────

ALL_ADAPTERS: dict[str, tuple[Any, str]] = {
    "cuad":        (_ingest_cuad,        "cuad_dataset.jsonl"),
    "ledgar":      (_ingest_ledgar,      "ledgar_dataset.jsonl"),
    "contractnli": (_ingest_contractnli, "contractnli_dataset.jsonl"),
}

_NOT_CLASSIFIERS = {
    "multilexsum":      "allenai/multi_lexsum        — suited for summarization RAG, not clause risk",
    "lawstackexchange": "ymoslem/Law-StackExchange    — suited for legal Q&A RAG, not clause risk",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest public legal datasets → ContractIQ training JSONL.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--datasets",
        default="cuad,ledgar,contractnli",
        help=(
            "Comma-separated list of datasets to ingest.\n"
            "  Available: cuad, ledgar, contractnli\n"
            "  Default: all three"
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Max examples to extract per dataset (0 = no limit). Default: 5000",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for output JSONL files. Default: training/",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    row_limit = max(args.limit, 0)

    requested_raw = [d.strip().lower() for d in args.datasets.split(",") if d.strip()]

    # Warn about datasets that exist but are not used for classification
    for name in requested_raw:
        if name in _NOT_CLASSIFIERS:
            print(
                f"[WARN] '{name}' is available on HuggingFace but is not a"
                f" clause risk classifier dataset:\n"
                f"       {_NOT_CLASSIFIERS[name]}\n"
                f"       Skipping from this run.\n"
            )

    requested = [d for d in requested_raw if d in ALL_ADAPTERS]
    unknown = [d for d in requested_raw if d not in ALL_ADAPTERS and d not in _NOT_CLASSIFIERS]
    if unknown:
        parser.error(
            f"Unknown dataset(s): {unknown}. "
            f"Available for classification: {sorted(ALL_ADAPTERS)}"
        )
    if not requested:
        parser.error("No supported classification datasets specified.")

    print(
        f"\nContractIQ dataset ingestion\n"
        f"  datasets : {', '.join(requested)}\n"
        f"  row limit: {row_limit or 'unlimited'} per dataset\n"
        f"  output   : {output_dir}\n"
        f"{'─' * 55}"
    )

    total = 0
    created_paths: list[str] = []

    for name in requested:
        fn, filename = ALL_ADAPTERS[name]
        out_path = output_dir / filename
        print(f"\n[{name.upper()}]")
        count = fn(row_limit, out_path)
        print(f"  → {count:,} examples saved to {out_path}")
        total += count
        if count > 0:
            created_paths.append(str(out_path))

    print(f"\n{'─' * 55}")
    print(f"  Total: {total:,} training examples across {len(created_paths)} file(s)")

    if created_paths:
        dataset_args = " \\\n      ".join(
            f"--dataset-path {p}" for p in created_paths
        )
        print(
            f"\nTo train with the new data:\n"
            f"  python -m training.train_legal_risk_model \\\n"
            f"      {dataset_args} \\\n"
            f"      --backend legal-bert"
        )


if __name__ == "__main__":
    main()
