from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split

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


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "models"
DEFAULT_SEED_DATASET = Path(__file__).with_name("seed_legal_risk_dataset.jsonl")
RISK_ORDER = {
    "COMPLIANT": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


def _read_dataset_file(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else payload.get("examples", [])

    normalized: list[dict[str, Any]] = []
    for row in rows:
        text = str(row.get("text", "")).strip()
        label = str(row.get("label", "")).strip().upper()
        if not text or label not in RISK_ORDER:
            continue
        normalized.append(
            {
                "text": text,
                "label": label,
                "clause_type": str(row.get("clause_type", "Unknown Clause")).strip() or "Unknown Clause",
                "source": str(row.get("source", path.name)).strip() or path.name,
            }
        )
    return normalized


def load_training_examples(dataset_paths: list[Path] | None = None) -> list[dict[str, Any]]:
    paths = dataset_paths or [DEFAULT_SEED_DATASET]
    examples: list[dict[str, Any]] = []
    for path in paths:
        examples.extend(_read_dataset_file(path))

    if not examples:
        raise RuntimeError("No valid training examples were found.")
    return examples


def _compose_text(example: dict[str, Any]) -> str:
    return f"{example['clause_type']}\n{example['text']}".strip()


def _stratify_or_none(labels: list[str]) -> list[str] | None:
    counts = Counter(labels)
    if len(counts) < 2:
        return None
    if min(counts.values()) < 2:
        return None
    return labels


def _train_tfidf_model(train_texts: list[str], train_labels: list[str]) -> dict[str, Any]:
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
    train_matrix = vectorizer.fit_transform(train_texts)
    classifier = LogisticRegression(max_iter=1200, class_weight="balanced")
    classifier.fit(train_matrix, train_labels)
    return {
        "backend": "tfidf",
        "vectorizer": vectorizer,
        "classifier": classifier,
        "embedder_model_name": None,
    }


def _train_sentence_transformer_model(train_texts: list[str], train_labels: list[str], model_name: str) -> dict[str, Any]:
    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers is not available in this environment.")
    embedder = SentenceTransformer(model_name)
    train_vectors = embedder.encode(train_texts, normalize_embeddings=True, show_progress_bar=False)
    classifier = LogisticRegression(max_iter=1200, class_weight="balanced")
    classifier.fit(train_vectors, train_labels)
    return {
        "backend": "sentence-transformer",
        "vectorizer": None,
        "classifier": classifier,
        "embedder_model_name": model_name,
    }


def _encode_legal_bert_batch(tokenizer: Any, model: Any, texts: list[str], batch_size: int = 32) -> "np.ndarray":
    """Mean-pool the last hidden state from a Legal-BERT / BERT model."""
    import torch as _torch
    all_embeddings: list["np.ndarray"] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        encoded = tokenizer(
            batch,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        with _torch.no_grad():
            output = model(**encoded)
        token_embeds = output.last_hidden_state  # (batch, seq, hidden)
        mask = encoded["attention_mask"].unsqueeze(-1).expand(token_embeds.size()).float()
        pooled = (token_embeds * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
        all_embeddings.append(pooled.cpu().numpy())
    return np.vstack(all_embeddings)


def _train_legal_bert_model(train_texts: list[str], train_labels: list[str], model_name: str) -> dict[str, Any]:
    """Fine a LogisticRegression probe on top of frozen Legal-BERT embeddings."""
    if torch is None or AutoTokenizer is None or AutoModel is None:
        raise RuntimeError(
            "'transformers' and 'torch' are required for the legal-bert backend. "
            "Install them with: pip install transformers torch"
        )
    print(f"  Loading Legal-BERT model '{model_name}' (first run downloads ~440 MB) ...")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    model.eval()
    print(f"  Encoding {len(train_texts)} training examples ...")
    train_vectors = _encode_legal_bert_batch(tokenizer, model, train_texts)
    classifier = LogisticRegression(max_iter=2000, class_weight="balanced")
    classifier.fit(train_vectors, train_labels)
    return {
        "backend": "legal-bert",
        "vectorizer": None,
        "classifier": classifier,
        "embedder_model_name": model_name,
    }


def _predict_probabilities(artifact: dict[str, Any], texts: list[str]) -> np.ndarray:
    backend = artifact.get("backend", "tfidf")

    if backend == "tfidf":
        features = artifact["vectorizer"].transform(texts)
        return artifact["classifier"].predict_proba(features)

    if backend == "sentence-transformer":
        if SentenceTransformer is None:
            raise RuntimeError("sentence-transformers is not available in this environment.")
        embedder = SentenceTransformer(artifact["embedder_model_name"])
        vectors = embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return artifact["classifier"].predict_proba(vectors)

    if backend == "legal-bert":
        if torch is None or AutoTokenizer is None or AutoModel is None:
            raise RuntimeError("'transformers' and 'torch' are required for the legal-bert backend.")
        model_name = artifact["embedder_model_name"]
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModel.from_pretrained(model_name)
        model.eval()
        vectors = _encode_legal_bert_batch(tokenizer, model, texts)
        return artifact["classifier"].predict_proba(vectors)

    raise ValueError(f"Unknown backend: {backend!r}")


def train_and_save_model(
    dataset_paths: list[Path] | None = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    backend: str = "tfidf",
    sentence_model_name: str = "all-MiniLM-L6-v2",
    test_size: float = 0.25,
) -> dict[str, Any]:
    examples = load_training_examples(dataset_paths)
    texts = [_compose_text(example) for example in examples]
    labels = [example["label"] for example in examples]

    x_train, x_test, y_train, y_test = train_test_split(
        texts,
        labels,
        test_size=test_size,
        random_state=42,
        stratify=_stratify_or_none(labels),
    )

    if backend == "sentence-transformer":
        eval_artifact = _train_sentence_transformer_model(x_train, y_train, sentence_model_name)
    elif backend == "legal-bert":
        eval_artifact = _train_legal_bert_model(x_train, y_train, sentence_model_name)
    else:
        eval_artifact = _train_tfidf_model(x_train, y_train)

    probabilities = _predict_probabilities(eval_artifact, x_test)
    classes = list(eval_artifact["classifier"].classes_)
    predictions = [classes[int(np.argmax(row))] for row in probabilities]
    accuracy = accuracy_score(y_test, predictions)
    report = classification_report(y_test, predictions, output_dict=True, zero_division=0)

    if backend == "sentence-transformer":
        final_artifact = _train_sentence_transformer_model(texts, labels, sentence_model_name)
    elif backend == "legal-bert":
        final_artifact = _train_legal_bert_model(texts, labels, sentence_model_name)
    else:
        final_artifact = _train_tfidf_model(texts, labels)

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "legal_risk_model.joblib"
    metrics_path = output_dir / "legal_risk_model_metrics.json"

    artifact_payload = {
        **final_artifact,
        "risk_order": RISK_ORDER,
        "training_examples": len(examples),
        "label_distribution": dict(sorted(Counter(labels).items())),
        "dataset_paths": [str(path) for path in (dataset_paths or [DEFAULT_SEED_DATASET])],
    }
    joblib.dump(artifact_payload, model_path)

    metrics_payload = {
        "backend": backend,
        "sentence_model_name": sentence_model_name if backend == "sentence-transformer" else None,
        "training_examples": len(examples),
        "label_distribution": dict(sorted(Counter(labels).items())),
        "accuracy": round(float(accuracy), 4),
        "classification_report": report,
        "model_path": str(model_path),
    }
    metrics_path.write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")
    return metrics_payload


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train a legal clause risk classifier for ContractIQ.")
    parser.add_argument(
        "--dataset-path",
        action="append",
        default=[],
        help="Path to a JSON or JSONL dataset with text/label/clause_type fields. Can be passed multiple times.",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for trained model artifacts.")
    parser.add_argument(
        "--backend",
        choices=["tfidf", "sentence-transformer", "legal-bert"],
        default="tfidf",
        help=(
            "Feature backend to train with.\n"
            "  tfidf              - Fast, reliable, no GPU required (default)\n"
            "  sentence-transformer - all-MiniLM-L6-v2 or similar bi-encoder\n"
            "  legal-bert         - nlpaueb/legal-bert-base-uncased, best accuracy"
        ),
    )
    parser.add_argument(
        "--sentence-model-name",
        default="nlpaueb/legal-bert-base-uncased",
        help=(
            "HuggingFace model name used when backend=sentence-transformer or legal-bert.\n"
            "  Default: nlpaueb/legal-bert-base-uncased"
        ),
    )
    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()
    dataset_paths = [Path(item).resolve() for item in args.dataset_path] or [DEFAULT_SEED_DATASET]
    metrics = train_and_save_model(
        dataset_paths=dataset_paths,
        output_dir=Path(args.output_dir).resolve(),
        backend=args.backend,
        sentence_model_name=args.sentence_model_name,
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()