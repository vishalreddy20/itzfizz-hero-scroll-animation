from __future__ import annotations

import re
from datetime import datetime

TAXONOMY_MAP: list[tuple[str, list[str]]] = [
    ("Definitions & Interpretation", ["definition", "interpretation", "defined term"]),
    ("Scope of Services / Deliverables", ["scope", "services", "deliverable", "statement of work"]),
    ("Term & Termination", ["term", "terminate", "termination", "expiry", "expiration"]),
    ("Payment Terms & Invoicing", ["payment", "invoice", "fees", "charges", "billing"]),
    ("Intellectual Property Ownership", ["intellectual property", "ownership", "work product", "assignment"]),
    ("License Grant & Restrictions", ["license", "licensed", "restriction", "permitted use"]),
    ("Confidentiality & NDA", ["confidential", "nda", "non-disclosure"]),
    ("Indemnification", ["indemnify", "indemnification", "defend", "hold harmless"]),
    ("Limitation of Liability", ["limitation of liability", "liability cap", "consequential"]),
    ("Warranty & Disclaimer", ["warranty", "disclaimer", "as is"]),
    ("Data Privacy & Security (GDPR / CCPA)", ["data", "privacy", "security", "gdpr", "ccpa", "breach", "dpa"]),
    ("Governing Law & Jurisdiction", ["governing law", "jurisdiction", "venue"]),
    ("Dispute Resolution & Arbitration", ["dispute", "arbitration", "aaa", "mediation"]),
    ("Force Majeure", ["force majeure", "act of god"]),
    ("Assignment & Subcontracting", ["assignment", "subcontract"]),
    ("Non-Solicitation & Non-Compete", ["non-solicit", "non compete", "non-compete"]),
    ("Audit Rights", ["audit", "inspect books"]),
    ("Insurance Requirements", ["insurance", "coverage"]),
    ("Entire Agreement & Amendments", ["entire agreement", "amendment", "modification"]),
    ("Notice Requirements", ["notice", "notices"]),
    ("Severability & Waiver", ["severability", "waiver"]),
    ("Most Favored Nation (MFN)", ["mfn", "most favored nation"]),
    ("SLA & Penalties", ["sla", "service level", "uptime", "penalty", "credit"]),
    ("Change Order Process", ["change order", "change request"]),
    ("Exclusivity Clauses", ["exclusive", "exclusivity"]),
]

DEFAULT_EXPECTED = [
    "Scope of Services / Deliverables",
    "Term & Termination",
    "Payment Terms & Invoicing",
    "Confidentiality & NDA",
    "Indemnification",
    "Limitation of Liability",
    "Data Privacy & Security (GDPR / CCPA)",
    "Governing Law & Jurisdiction",
]


def extract_clauses(contract_text: str) -> dict:
    blocks = _split_into_clause_blocks(contract_text)
    clauses = []

    for idx, block in enumerate(blocks, start=1):
        heading, original_text = block
        clause_type = classify_clause_type(f"{heading}\n{original_text}")
        clauses.append(
            {
                "clause_id": f"C{idx:03d}",
                "clause_type": clause_type,
                "heading": heading,
                "original_text": original_text,
                "position": _position_from_index(idx, len(blocks)),
                "word_count": len(original_text.split()),
                "contains_defined_terms": bool(re.search(r'"[A-Za-z0-9 _-]+"', original_text)),
                "cross_references": _extract_cross_refs(original_text),
                "extraction_confidence": "HIGH" if heading != "[AMBIGUOUS]" else "MEDIUM",
                "extraction_notes": "" if heading != "[AMBIGUOUS]" else "[AMBIGUOUS] Unable to clearly identify heading boundary.",
            }
        )

    contract_metadata = {
        "contract_type": detect_contract_type(contract_text),
        "parties": detect_parties(contract_text),
        "effective_date": detect_effective_date(contract_text),
        "governing_law": detect_governing_law(contract_text),
        "total_clauses_found": len(clauses),
        "missing_standard_clauses": _find_missing_clause_types(clauses),
    }

    return {
        "contract_metadata": contract_metadata,
        "clauses": clauses,
    }


def detect_contract_type(contract_text: str) -> str:
    lowered = contract_text.lower()
    if "master service" in lowered or "msa" in lowered:
        return "MSA"
    if "non-disclosure" in lowered or "confidentiality agreement" in lowered or "nda" in lowered:
        return "NDA"
    if "software as a service" in lowered or "saas" in lowered:
        return "SaaS Agreement"
    if "statement of work" in lowered or "sow" in lowered:
        return "SOW"
    return "Unknown"


def detect_parties(contract_text: str) -> list[str]:
    pattern = re.compile(
        r"between\s+([A-Za-z0-9 ,.&'\-]+?)\s+and\s+([A-Za-z0-9 ,.&'\-]+?)(?:\.|,|\n)",
        flags=re.IGNORECASE,
    )
    match = pattern.search(contract_text)
    if not match:
        return ["Unknown Party A", "Unknown Party B"]
    return [match.group(1).strip(), match.group(2).strip()]


def detect_effective_date(contract_text: str) -> str:
    patterns = [
        r"effective date\s*[:\-]?\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})",
        r"dated\s*[:\-]?\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})",
        r"(\d{4}-\d{2}-\d{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, contract_text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return datetime.utcnow().date().isoformat()


def detect_governing_law(contract_text: str) -> str:
    match = re.search(r"govern(?:ed|ing)\s+by\s+the\s+laws\s+of\s+([A-Za-z ]+)", contract_text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip().rstrip(".")

    fallback = re.search(r"governing law\s*[:\-]?\s*([A-Za-z ]+)", contract_text, flags=re.IGNORECASE)
    if fallback:
        return fallback.group(1).strip().rstrip(".")

    return "Unknown"


def classify_clause_type(text: str) -> str:
    lowered = text.lower()
    for clause_type, keywords in TAXONOMY_MAP:
        if any(keyword in lowered for keyword in keywords):
            return clause_type
    heading_line = text.splitlines()[0].strip()
    return f"CUSTOM: {heading_line[:60]}" if heading_line else "CUSTOM: Unlabeled Clause"


def _split_into_clause_blocks(text: str) -> list[tuple[str, str]]:
    lines = [line.rstrip() for line in text.splitlines()]
    indices: list[int] = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        numbered = bool(re.match(r"^(\d+([.]\d+)*)[.)]?\s+.+", stripped))
        heading_case = bool(re.match(r"^[A-Z][A-Z0-9 /&,-]{3,}$", stripped))
        if numbered or heading_case:
            indices.append(i)

    if not indices:
        return [("[AMBIGUOUS]", text.strip())]

    blocks: list[tuple[str, str]] = []
    for idx, start in enumerate(indices):
        end = indices[idx + 1] if idx + 1 < len(indices) else len(lines)
        clause_lines = lines[start:end]
        heading = clause_lines[0].strip() or "[AMBIGUOUS]"
        body = "\n".join(clause_lines).strip()
        if body:
            blocks.append((heading, body))

    return blocks


def _extract_cross_refs(text: str) -> list[str]:
    refs = re.findall(r"Section\s+\d+(?:\.\d+)*", text, flags=re.IGNORECASE)
    unique_refs: list[str] = []
    for ref in refs:
        normalized = ref.strip()
        if normalized not in unique_refs:
            unique_refs.append(normalized)
    return unique_refs


def _position_from_index(index: int, total: int) -> str:
    if total <= 2:
        return "beginning" if index == 1 else "end"
    ratio = index / total
    if ratio <= 0.33:
        return "beginning"
    if ratio <= 0.66:
        return "middle"
    return "end"


def _find_missing_clause_types(clauses: list[dict]) -> list[str]:
    present = {c["clause_type"] for c in clauses}
    return [expected for expected in DEFAULT_EXPECTED if expected not in present]
