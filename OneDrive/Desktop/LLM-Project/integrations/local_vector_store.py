from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


class LocalCollection:
    def __init__(self, base_path: Path, name: str) -> None:
        self.base_path = base_path
        self.name = name
        self.file = base_path / f"{name}.json"
        self.base_path.mkdir(parents=True, exist_ok=True)
        if not self.file.exists():
            self.file.write_text(json.dumps({"rows": []}, indent=2), encoding="utf-8")

    def _load(self) -> dict[str, Any]:
        return json.loads(self.file.read_text(encoding="utf-8"))

    def _save(self, payload: dict[str, Any]) -> None:
        self.file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def add(self, documents: list[str], embeddings: list[list[float]], metadatas: list[dict], ids: list[str]) -> None:
        payload = self._load()
        rows = payload["rows"]
        for document, embedding, metadata, row_id in zip(documents, embeddings, metadatas, ids):
            rows.append(
                {
                    "id": row_id,
                    "document": document,
                    "embedding": embedding,
                    "metadata": metadata,
                }
            )
        self._save(payload)

    def query(self, query_embeddings: list[list[float]], n_results: int = 3, include: list[str] | None = None) -> dict:
        payload = self._load()
        rows = payload["rows"]
        if not rows:
            return {"documents": [[]], "metadatas": [[]], "ids": [[]]}

        query = np.array(query_embeddings[0], dtype=float)
        query_norm = np.linalg.norm(query)

        scored: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            emb = np.array(row["embedding"], dtype=float)
            denom = (np.linalg.norm(emb) * query_norm) or 1.0
            sim = float(np.dot(emb, query) / denom)
            scored.append((sim, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:n_results]

        return {
            "documents": [[row["document"] for _, row in top]],
            "metadatas": [[row["metadata"] for _, row in top]],
            "ids": [[row["id"] for _, row in top]],
        }


class LocalVectorStore:
    def __init__(self, path: str) -> None:
        self.base_path = Path(path)

    def get_or_create_collection(self, name: str) -> LocalCollection:
        return LocalCollection(self.base_path, name)
