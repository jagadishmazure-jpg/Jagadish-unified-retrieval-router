"""Print what this router does that the sibling data-agent repos do not:
one question -> SQL, RAG or BOTH with a cited reason, a per-claim merge that
flags numeric conflicts, and a role-scoped gateway enforced by SQLite itself."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from router import router, seed, views  # noqa: E402

idx = router.default_index()
for q, role in [("How many open tickets do we have?", "analyst"),
                ("What is our return policy?", "analyst"),
                ("How many open tickets do we have and what is the escalation policy?", "support_lead")]:
    r = router.answer(q, role, corpus_index=idx)
    conflicts = [f"{c['subject']} (sql {c['sql_value']} vs docs {c['rag_value']})" for c in r["conflicts"]]
    print(f"{r['route']:4} {r['reason_id']:<13} {q}")
    if conflicts:
        print(f"     CONFLICT flagged on: {', '.join(conflicts)}")

con = seed.seed_db()
views.create_views(con)
for sql in ("SELECT * FROM v_ticket_backlog, employees", "SELECT * FROM v_salaries"):
    try:
        views.run_readonly(con, sql, allowed_views=views.ALLOWED_VIEWS - {"v_salaries"})
        print("ALLOWED", sql)
    except views.GatewayError as e:
        print(f"denied  {sql} -> {e}")
