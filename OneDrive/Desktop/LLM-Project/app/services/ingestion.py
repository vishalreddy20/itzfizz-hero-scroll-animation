from __future__ import annotations

import io
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from app.services.runtime_config import get_runtime_profile


SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx"}


class IngestionSecurityError(ValueError):
    pass


def extract_text_from_upload(filename: str, content: bytes) -> str:
    _validate_upload_safety(filename, content)
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix}")

    if suffix == ".txt":
        text = content.decode("utf-8", errors="replace")
    elif suffix == ".pdf":
        text = _extract_pdf_text(content)
    else:
        text = _extract_docx_text(content)

    text = text.strip()
    if not text:
        raise ValueError("No text could be extracted from the uploaded file.")
    return text


def _extract_pdf_text(content: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(content))
        pages: list[str] = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        return "\n\n".join(pages)
    except Exception as exc:
        raise ValueError("Unable to parse PDF content safely") from exc


def _extract_docx_text(content: bytes) -> str:
    try:
        document = Document(io.BytesIO(content))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    except Exception as exc:
        raise ValueError("Unable to parse DOCX content safely") from exc


def _validate_upload_safety(filename: str, content: bytes) -> None:
    profile = get_runtime_profile()
    if len(content) > profile.max_upload_bytes:
        raise IngestionSecurityError(f"Uploaded file exceeds max size of {profile.max_upload_bytes} bytes")
    if b"\x00" in content[:2048]:
        raise IngestionSecurityError("Binary file signatures detected in upload")

    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf" and not content.startswith(b"%PDF"):
        raise IngestionSecurityError("File extension/type mismatch: expected PDF signature")
    if suffix == ".docx" and not content.startswith(b"PK"):
        raise IngestionSecurityError("File extension/type mismatch: expected DOCX/ZIP signature")
    if suffix == ".txt" and _binary_ratio(content) > 0.15:
        raise IngestionSecurityError("Text upload appears to be binary or malformed")


def _binary_ratio(content: bytes) -> float:
    if not content:
        return 0.0
    non_printable = 0
    check = content[:4096]
    for byte in check:
        if byte in (9, 10, 13):
            continue
        if byte < 32 or byte > 126:
            non_printable += 1
    return non_printable / max(1, len(check))
