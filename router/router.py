"""The data-agent router: classify -> govern -> execute -> merge -> audit.

Governance is enforced at routing time: every target view and doc set is
policy-checked BEFORE any source is touched. Denials are audited, then
raised with the policy ID cited.
"""

from __future__ import annotations

from pathlib import Path

from . import audit, classify, corpus, govern, merge, rag, seed, views

FIXED_SQL = {
    "v_order_summary": "SELECT * FROM v_order_summary",
    "v_inventory_status": "SELECT * FROM v_inventory_status",
    "v_ticket_backlog": "SELECT * FROM v_ticket_backlog",
    "v_salaries": "SELECT * FROM v_salaries",
}


def default_index() -> dict:
    docs_root = Path(__file__).resolve().parent.parent / "docs"
    return rag.build_index(corpus.load_corpus(docs_root))


def answer(question: str, role: str = "analyst", con=None,
           corpus_index: dict | None = None, log: dict | None = None) -> dict:
    if con is None:
        con = seed.seed_db()
    views.create_views(con)
    if corpus_index is None:
        corpus_index = default_index()

    decision = classify.classify(question)
    checks: list[dict] = []
    try:
        for v in decision["sql_views"]:
            govern.check(role, "view", v)
            checks.append({"target": v, "kind": "view", "decision": "allow"})
        for d in decision["doc_sets"]:
            govern.check(role, "docset", d)
            checks.append({"target": d, "kind": "docset", "decision": "allow"})
    except govern.AccessDenied as e:
        if log is not None:
            audit.record(
                log,
                {"question": question, "role": role,
                 "route": decision["route"], "reason_id": decision["reason_id"],
                 "policy_checks": checks + [{"denied": e.detail, "policy_id": e.policy_id}],
                 "outcome": "denied"},
            )
        raise

    sql_claims: list[dict] = []
    rag_claims: list[dict] = []
    if decision["route"] in ("sql", "both"):
        for v in decision["sql_views"]:
            cols, rows, _truncated = views.run_readonly(
                con, FIXED_SQL[v], allowed_views=govern.ROLE_VIEWS[role])
            sql_claims.extend(merge.to_sql_claims(v, cols, rows))
    if decision["route"] in ("rag", "both"):
        chunks = rag.search(corpus_index, question,
                            allowed_sets=set(decision["doc_sets"]))
        rag_claims.extend(merge.to_rag_claims(chunks))

    claims = sql_claims + rag_claims
    conflicts = merge.find_conflicts(sql_claims, rag_claims)
    text = merge.render(claims, conflicts)

    if log is not None:
        audit.record(
            log,
            {"question": question, "role": role,
             "route": decision["route"], "reason_id": decision["reason_id"],
             "reason": decision["reason"], "policy_checks": checks,
             "sources": {"sql_views": decision["sql_views"],
                         "doc_sets": decision["doc_sets"]},
             "n_claims": len(claims), "n_conflicts": len(conflicts),
             "outcome": "answered"},
        )
    return {
        "question": question, "role": role, "route": decision["route"],
        "reason_id": decision["reason_id"], "reason": decision["reason"],
        "claims": claims, "conflicts": conflicts, "answer": text,
    }
