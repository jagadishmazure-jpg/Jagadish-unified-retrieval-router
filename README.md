# Jagadish Unified Retrieval Router

A data-agent retrieval router: one question goes to SQL, to documents, or to
both -- with role-based governance enforced *before* any source is touched,
per-claim citations on every answer, and conflicts flagged instead of
silently resolved.

> **Disclaimer.** Independent portfolio project, not affiliated with any
> company. All data is synthetic and fictional (Calvessa Goods). Nothing
> here is production advice.

## Recruiter summary

- **Problem:** enterprise questions span structured data (SQL) and
  unstructured data (docs); somebody must decide which sources to trust,
  with access control enforced at routing time.
- **Approach:** deterministic classifier (SQL / RAG / BOTH with cited
  reason IDs) -> role x source policy checks -> hardened SQL gateway +
  TF-IDF retrieval -> citation merge with conflict flags -> hash-chained
  audit of every routing decision.
- **Proof:** 52 tests green (stdlib only). Live run: "How many open tickets
  and what is the escalation policy?" routes BOTH, finds SQL=5 vs docs~=10,
  flags CONFLICT with both citations; `analyst` asking for salaries is
  denied with POL-ACCESS-01 and the denial is audited.

## How this differs from text2sql-data-agent

`text2sql-data-agent` is a single-source layer: natural language to SQL,
with repair retries. This repo is the layer *above* it: it decides **which**
sources a question needs at all. text2sql answers "how many tickets";
the router answers "how many tickets *and* what does the policy say" by
fanning out to SQL and docs, governing each, and merging with citations.
The two compose: the router could call text2sql as its SQL engine.

## How it works

1. `classify.classify(question)` -> `{"route", "reason_id", "reason", ...}`
   (e.g. ROUTE-BOTH-01: quantity words + entity + policy signal).
2. `govern.check(role, kind, name)` for every target; denials raise
   `AccessDenied` citing POL-ACCESS-01/02 *before* any query runs.
3. SQL via `views.run_readonly`: text allowlist (SEC-SELECT-01/02/03) +
   strict view-aware authorizer + `fetchmany` cap.
4. Docs via `rag.search`: TF-IDF over SOPs and (role permitting) emails,
   cited as `file §section`.
5. `merge`: every claim cited; numeric conflicts prefer SQL (MERGE-NUM-01)
   but stay visible.
6. `audit.record`: the full decision appended to a hash-chained log.

## Real run

```
Q: How many open tickets do we have and what is the escalation policy?
route: both | reason: ROUTE-BOTH-01
- open tickets: 5 [sql:v_ticket_backlog]
- Current volume: Current open ticket volume is approximately 10 across all
  queues. ... [support-escalation.md §Current volume]
CONFLICT on open tickets: SQL says 5 [sql:v_ticket_backlog], docs say 10
[support-escalation.md §Current volume]. structured source preferred for
numeric values (MERGE-NUM-01).
```

## Run it

```bash
python3 -m pytest tests/ -q        # 52 tests
python3 scripts/count_tests.py     # prints the real total
streamlit run demo/app.py          # thin demo (pip install streamlit)
```

## Knowledge

- [knowledge/domain-notes.md](knowledge/domain-notes.md) -- the data-agent
  retrieval pattern, distilled
- [knowledge/architecture.md](knowledge/architecture.md) -- Mermaid diagram

## Guardrails

- Governance before retrieval (POL-ACCESS-00/01/02); denials audited.
- Strict view-aware SQLite authorizer: backing tables readable only via
  view expansion, never when explicitly named (tested with text check off).
- `fetchmany(ROW_CAP+1)` cap; no `fetchall()` on planner paths.
- Hash-chained audit log; `audit.verify()` detects tampering.
- Conflicts surfaced (MERGE-NUM-01), never silently resolved.

## Limitations and known failures

- Fixed per-view SQL templates, not full text-to-SQL (routing is the focus).
- Rule-based classifier: 52 regression checks, not a quality claim; odd
  phrasings fall back to RAG (ROUTE-RAG-02).
- TF-IDF retrieval; fine for 10 docs, not for 10M.
- `role` is caller-supplied; production needs real authN (OIDC).
- In-memory SQLite; no persistence.

## Built / Written-not-run / Planned

| Status | Item |
|---|---|
| Built | Classifier (SQL/RAG/BOTH + cited reasons), governance, merge with conflict flags, hardened gateway, TF-IDF RAG, hash-chained audit, demo, 52 tests |
| Written-not-run | Streamlit demo (needs `pip install streamlit`; logic fully tested in `demo_helpers`) |
| Planned | LLM synthesis over cited claims; OIDC roles; async retrieval with latency budgets |

## Related repos

- `Jagadish-text2sql-data-agent` -- the single-source NL-to-SQL layer this
  router sits above (composes: router -> text2sql as SQL engine).
- `Jagadish-agent-feedback-loop` -- closing the loop on retrieved answers.
