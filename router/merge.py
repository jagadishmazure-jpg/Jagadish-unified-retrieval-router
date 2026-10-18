"""Merge SQL and RAG answers with per-claim citations.

Conflict rule: when both sources give a NUMBER for the same subject and
they disagree, the structured source wins (MERGE-NUM-01) -- but the
conflict is always surfaced in the output. Never silently pick.
"""

from __future__ import annotations

import re

MERGE_NUM_RULE = "MERGE-NUM-01"


def to_sql_claims(view: str, columns: list[str], rows: list) -> list[dict]:
    claims = []
    if view == "v_ticket_backlog":
        claims.append(
            {"subject": "open tickets", "value": str(len(rows)),
             "kind": "number", "citation": f"sql:{view}"}
        )
    elif view == "v_order_summary":
        # Cancelled orders are not revenue (MERGE-REV-01); pending is booked.
        total = sum(float(r["revenue"] or 0) for r in rows if r["status"] != "cancelled")
        claims.append(
            {"subject": "total revenue", "value": f"{total:.2f}",
             "kind": "number", "citation": f"sql:{view} (excl. cancelled)"}
        )
        for r in rows:
            claims.append(
                {"subject": f"{r['status']} orders", "value": str(r["n"]),
                 "kind": "number", "citation": f"sql:{view}"}
            )
    elif view == "v_inventory_status":
        low = sum(1 for r in rows if r["flag"] == "low")
        claims.append(
            {"subject": "low-stock SKUs", "value": str(low),
             "kind": "number", "citation": f"sql:{view}"}
        )
    elif view == "v_salaries":
        avg = sum(float(r["salary"]) for r in rows) / max(len(rows), 1)
        claims.append(
            {"subject": "average salary", "value": f"{avg:.2f}",
             "kind": "number", "citation": f"sql:{view}"}
        )
    return claims


def to_rag_claims(chunks: list[dict]) -> list[dict]:
    return [
        {"subject": c["section"], "value": c["text"][:200],
         "kind": "fact", "citation": c["citation"]}
        for c in chunks
    ]


def _kw_match(keyword: str, window: str) -> bool:
    if keyword in window:
        return True
    # light plural handling: "tickets" matches "ticket"
    return keyword.endswith("s") and keyword[:-1] in window


def find_conflicts(sql_claims: list[dict], rag_claims: list[dict]) -> list[dict]:
    conflicts = []
    for sc in sql_claims:
        if sc["kind"] != "number":
            continue
        keywords = sc["subject"].lower().split()
        for rc in rag_claims:
            text = rc["value"].lower()
            hit = False
            for m in re.finditer(r"\d+(?:\.\d+)?", text):
                window = text[max(0, m.start() - 80): m.end() + 80]
                if all(_kw_match(k, window) for k in keywords) and m.group(0) != sc["value"]:
                    conflicts.append(
                        {
                            "subject": sc["subject"],
                            "sql_value": sc["value"],
                            "sql_citation": sc["citation"],
                            "rag_value": m.group(0),
                            "rag_citation": rc["citation"],
                            "resolution": (
                                "structured source preferred for numeric values "
                                f"({MERGE_NUM_RULE})"
                            ),
                            "flagged": True,
                        }
                    )
                    hit = True
                    break
            if hit:
                break
    return conflicts


def render(claims: list[dict], conflicts: list[dict]) -> str:
    lines = []
    for c in claims:
        lines.append(f"- {c['subject']}: {c['value']} [{c['citation']}]")
    for cf in conflicts:
        lines.append(
            f"CONFLICT on {cf['subject']}: SQL says {cf['sql_value']} "
            f"[{cf['sql_citation']}], docs say {cf['rag_value']} "
            f"[{cf['rag_citation']}]. {cf['resolution']}."
        )
    return "\n".join(lines)
