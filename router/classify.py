"""Deterministic question classifier: SQL-only, RAG-only, or BOTH.

Every decision carries a cited reason ID so the audit log (and the user)
can see exactly why a route was chosen. Rule-based, no model calls --
routing determinism is the point.
"""

from __future__ import annotations

import re

ROUTE_SQL = "sql"
ROUTE_RAG = "rag"
ROUTE_BOTH = "both"

ENTITY_VIEWS = {
    "order": "v_order_summary",
    "orders": "v_order_summary",
    "revenue": "v_order_summary",
    "shipments": "v_order_summary",
    "inventory": "v_inventory_status",
    "stock": "v_inventory_status",
    "sku": "v_inventory_status",
    "skus": "v_inventory_status",
    "ticket": "v_ticket_backlog",
    "tickets": "v_ticket_backlog",
    "salary": "v_salaries",
    "salaries": "v_salaries",
    "pay": "v_salaries",
}

SQL_WORDS = [
    "how many", "how much", "total", "sum", "average",
    "count", "list", "show me", "what are the", "which",
]

RAG_WORDS = [
    "policy", "policies", "process", "procedure", "how do",
    "can we", "allowed", "guideline", "email", "thread",
    "said", "say", "wrote", "announced",
]

_EMAIL_WORDS = ("email", "thread", "said", "say", "wrote")


def classify(question: str) -> dict:
    q = question.lower()
    views: list[str] = []
    for word, view in ENTITY_VIEWS.items():
        if re.search(r"\b" + re.escape(word) + r"\b", q) and view not in views:
            views.append(view)
    sql_signal = any(w in q for w in SQL_WORDS)
    rag_signal = any(w in q for w in RAG_WORDS)

    doc_sets = ["sops"]
    if any(w in q for w in _EMAIL_WORDS):
        doc_sets.append("emails")

    if views and sql_signal and rag_signal:
        return _decision(
            ROUTE_BOTH, "ROUTE-BOTH-01",
            f"quantity words plus a structured entity ({', '.join(views)}) and a "
            "policy/process signal: both sources needed.",
            views, doc_sets,
        )
    if views and sql_signal:
        return _decision(
            ROUTE_SQL, "ROUTE-SQL-01",
            f"quantity words plus a structured entity ({', '.join(views)}): "
            "numbers live in the database.",
            views, [],
        )
    if rag_signal:
        return _decision(
            ROUTE_RAG, "ROUTE-RAG-01",
            "policy/process/email language: the answer lives in documents.",
            [], doc_sets,
        )
    if views:
        return _decision(
            ROUTE_SQL, "ROUTE-SQL-02",
            f"structured entity named ({', '.join(views)}) with no document signal: "
            "default to the database.",
            views, [],
        )
    return _decision(
        ROUTE_RAG, "ROUTE-RAG-02",
        "no structured entity or quantity signal: documents are the safe default.",
        [], doc_sets,
    )


def _decision(route: str, reason_id: str, reason: str,
              sql_views: list[str], doc_sets: list[str]) -> dict:
    return {
        "route": route,
        "reason_id": reason_id,
        "reason": reason,
        "sql_views": sql_views,
        "doc_sets": doc_sets,
    }
