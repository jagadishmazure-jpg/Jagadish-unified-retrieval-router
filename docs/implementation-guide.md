# Implementation guide

How to adopt (or extend) the unified retrieval router.

## Run it

```bash
python3 -m pytest tests/ -q          # 52 tests, stdlib only
python3 scripts/count_tests.py       # prints the real total
streamlit run demo/app.py            # thin demo (pip install streamlit)
```

## Answer a question in code

```python
from router import audit, router

log = audit.new_log()
res = router.answer(
    "How many open tickets do we have and what is the escalation policy?",
    role="support_lead",
    log=log,
)
print(res["route"])       # "both"
print(res["reason_id"])    # "ROUTE-BOTH-01"
print(res["answer"])      # claims with citations + CONFLICT flag
print(audit.verify(log))  # True
```

## Add a role

Edit `router/govern.py`: add the role to `ROLE_VIEWS` / `ROLE_DOCSETS`.
Denials automatically cite `POL-ACCESS-01` (views) or `POL-ACCESS-02`
(doc sets). Add a test in `tests/test_router.py` asserting the new
allow/deny matrix.

## Add a view

1. Add the table(s) in `router/seed.py`.
2. Add the view in `router/views.py::create_views` and register it in
   `ALLOWED_VIEWS` plus its backing tables in `VIEW_BACKING`.
3. Map entity keywords to it in `router/classify.py::ENTITY_VIEWS`.
4. Grant it to roles in `router/govern.py::ROLE_VIEWS`.
5. Add a headline claim in `router/merge.py::to_sql_claims`.

## Swap the classifier

`classify.classify` returns a plain dict
(`route`, `reason_id`, `reason`, `sql_views`, `doc_sets`). Replace the
rule set with a model call if you like -- the router, governance, merge,
and audit layers don't care, as long as every decision still carries a
`reason_id`.

## Production hardening (not built)

- Real authN (OIDC) instead of the `role` string.
- Per-tenant corpora and row-level security in views.
- Async retrieval with timeouts and per-source latency budgets.
- LLM synthesis over the cited claims (the router hands it evidence,
  not a blank prompt).
