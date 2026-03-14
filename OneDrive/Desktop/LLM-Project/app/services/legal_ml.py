from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from app.services.runtime_config import (
    get_legal_model_min_confidence,
    get_legal_model_path,
    is_legal_model_enabled,
)

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None

try:
    import torch
    from transformers import AutoModel, AutoTokenizer  # type: ignore
except Exception:
    torch = None  # type: ignore
    AutoModel = None  # type: ignore
    AutoTokenizer = None  # type: ignore


ROOT_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class LegalRiskPrediction:
    label: str
    confidence: float
    backend: str


@lru_cache(maxsize=1)
def _load_model(path_value: str) -> dict[str, Any] | None:
    path = Path(path_value)
    if not path.exists():
        return None
    payload = joblib.load(path)
    return payload if isinstance(payload, dict) else None


@lru_cache(maxsize=1)
def _load_embedder(model_name: str) -> Any:
    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers is not available in this environment.")
    return SentenceTransformer(model_name)


@lru_cache(maxsize=1)
def _load_legal_bert_tokenizer(model_name: str) -> Any:
    if AutoTokenizer is None:
        raise RuntimeError("'transformers' is not installed. Run: pip install transformers")
    return AutoTokenizer.from_pretrained(model_name)


@lru_cache(maxsize=1)
def _load_legal_bert_model(model_name: str) -> Any:
    if AutoModel is None:
        raise RuntimeError("'transformers' is not installed. Run: pip install transformers")
    m = AutoModel.from_pretrained(model_name)
    m.eval()
    return m


def _mean_pool_legal_bert(model_name: str, texts: list[str]) -> "np.ndarray":
    """Encode texts with Legal-BERT via mean pooling of the last hidden state."""
    import torch as _torch
    tokenizer = _load_legal_bert_tokenizer(model_name)
    model = _load_legal_bert_model(model_name)
    encoded = tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=512,
        return_tensors="pt",
    )
    with _torch.no_grad():
        output = model(**encoded)
    token_embeds = output.last_hidden_state
    mask = encoded["attention_mask"].unsqueeze(-1).expand(token_embeds.size()).float()
    pooled = (token_embeds * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
    return pooled.cpu().numpy()


def clear_model_cache() -> None:
    _load_model.cache_clear()
    _load_embedder.cache_clear()
    _load_legal_bert_tokenizer.cache_clear()
    _load_legal_bert_model.cache_clear()


def predict_clause_risk(clause_type: str, clause_text: str) -> LegalRiskPrediction | None:
    if not is_legal_model_enabled():
        return None

    model_path = get_legal_model_path(ROOT_DIR)
    artifact = _load_model(str(model_path.resolve()))
    if artifact is None:
        return None

    text = f"{clause_type}\n{clause_text}".strip()
    backend = str(artifact.get("backend", "tfidf"))
    classifier = artifact.get("classifier")
    if classifier is None:
        return None

    if backend == "tfidf":
        vectorizer = artifact.get("vectorizer")
        if vectorizer is None:
            return None
        features = vectorizer.transform([text])
        probabilities = classifier.predict_proba(features)[0]
    elif backend == "sentence-transformer":
        embedder_name = str(artifact.get("embedder_model_name", "all-MiniLM-L6-v2"))
        embedder = _load_embedder(embedder_name)
        vectors = embedder.encode([text], normalize_embeddings=True, show_progress_bar=False)
        probabilities = classifier.predict_proba(vectors)[0]
    elif backend == "legal-bert":
        if torch is None or AutoModel is None:
            return None
        embedder_name = str(artifact.get("embedder_model_name", "nlpaueb/legal-bert-base-uncased"))
        vectors = _mean_pool_legal_bert(embedder_name, [text])
        probabilities = classifier.predict_proba(vectors)[0]
    else:
        return None

    class_names = list(classifier.classes_)
    best_index = int(np.argmax(probabilities))
    confidence = float(probabilities[best_index])
    if confidence < get_legal_model_min_confidence():
        return None
    return LegalRiskPrediction(label=class_names[best_index], confidence=confidence, backend=backend)