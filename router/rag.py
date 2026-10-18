"""TF-IDF retrieval over the docs corpus with ``file §section`` citations."""

from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[a-z0-9]+")
# Question words carry no topic; without this list "what is our ..." ranks
# whichever chunk repeats "is"/"our" most (RAG-RANK-01).
_STOPWORDS = frozenset(
    "a an and are as at be by can do does for from has have how i in is it of on or our "
    "say said should the their this to was we what when where which who why will with "
    "you your about".split()
    # Routing words (classify.RAG_WORDS) say "look in the documents", not what
    # the topic is; scoring on them ranks any short policy chunk first.
    + "policy policies process procedure guideline guidelines rule rules".split()
)


def _stem(tok: str) -> str:
    """Very light plural folding so 'return' matches 'returns' (RAG-RANK-01)."""
    if len(tok) > 3 and tok.endswith("ies"):
        return tok[:-3] + "y"
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok


def _tokens(text: str) -> list[str]:
    return [_stem(t) for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


def build_index(corpus: list[dict]) -> dict:
    doc_freq: Counter = Counter()
    indexed = []
    for doc in corpus:
        # Title and section heading are indexed with the body: an email whose
        # topic is only in its subject line must still be findable (RAG-RANK-01).
        toks = _tokens(f"{doc.get('title', '')} {doc['section']} {doc['text']}")
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
