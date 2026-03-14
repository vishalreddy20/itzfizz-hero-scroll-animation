from __future__ import annotations

import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class PlaybookRule:
    def __init__(self, clause_name: str, body: str) -> None:
        self.clause_name = clause_name
        self.body = body


class PlaybookIndex:
    def __init__(self, rules: list[PlaybookRule]) -> None:
        self.rules = rules
        self.vectorizer = TfidfVectorizer(stop_words="english")
        corpus = [f"{rule.clause_name}\n{rule.body}" for rule in rules]
        self.matrix = self.vectorizer.fit_transform(corpus)

    def lookup(self, query: str) -> PlaybookRule | None:
        if not self.rules:
            return None
        vec = self.vectorizer.transform([query])
        scores = cosine_similarity(vec, self.matrix)[0]
        best_index = int(scores.argmax())
        if scores[best_index] <= 0:
            return None
        return self.rules[best_index]


def load_playbook(path: Path) -> PlaybookIndex:
    raw = path.read_text(encoding="utf-8")
    rules = _parse_rules(raw)
    return PlaybookIndex(rules)


def _parse_rules(raw: str) -> list[PlaybookRule]:
    blocks = re.split(r"\n\s*CLAUSE:\s*", raw)
    rules: list[PlaybookRule] = []

    for block in blocks[1:]:
        lines = block.strip().splitlines()
        if not lines:
            continue
        clause_name = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        rules.append(PlaybookRule(clause_name=clause_name, body=body))

    return rules
