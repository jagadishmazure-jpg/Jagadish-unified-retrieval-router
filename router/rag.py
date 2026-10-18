"""TF-IDF retrieval over the docs corpus with ``file §section`` citations."""

from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def build_index(corpus: list[dict]) -> dict:
    doc_freq: Counter = Counter()
    indexed = []
    for doc in corpus:
        toks = _tokens(doc["text"])
        tf = Counter(toks)
        indexed.append((doc, tf, max(len(toks), 1)))
        for t in set(toks):
            doc_freq[t] += 1
    return {"docs": indexed, "df": doc_freq, "n": len(indexed)}


def search(index: dict, query: str, top_k: int = 3,
           allowed_sets: set[str] | None = None) -> list[dict]:
    qtoks = _tokens(query)
    if not qtoks:
        return []
    results = []
    for doc, tf, length in index["docs"]:
        if allowed_sets is not None and doc["set"] not in allowed_sets:
            continue
        score = 0.0
        for t in set(qtoks):
            if t not in tf:
                continue
            idf = math.log((index["n"] + 1) / (index["df"][t] + 1)) + 1.0
            score += (tf[t] / length) * idf
        if score > 0:
            results.append(
                {
                    "doc": doc["doc"],
                    "section": doc["section"],
                    "text": doc["text"],
                    "citation": doc["citation"],
                    "score": round(score, 4),
                }
            )
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_k]
