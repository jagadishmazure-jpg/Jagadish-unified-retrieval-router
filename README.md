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
- **Proof:** the suite runs on stdlib only; the real total is printed by
  `scripts/count_tests.py` below. Live run: "How many open tickets and what
  is the escalation policy?" routes BOTH, finds SQL=5 vs docs~=10, flags
  CONFLICT with both citations; `analyst` asking for salaries is denied
  with POL-ACCESS-01 and the denial is audited.

## How this differs from the earlier data-agent repos

| Repo | What it owns | What this router does not repeat |
|---|---|---|
| `Jagadish-text2sql-data-agent` | Natural language to SQL generation, a 15-question gold set, repair retries | The router generates no SQL; each view has one fixed template |
| `Jagadish-agentic-data-layer` | Bronze/silver/gold data products and their contracts | No data products; the router reads views that already exist |
| `Jagadish-agentic-rag` | Graph-based retrieval | Plain TF-IDF; retrieval quality is not the focus here |
| `Jagadish-governed-data-agent` | Deny-first role checks across SQL and documents, rule-cited denials, hash-chained ledger | **Overlap, stated honestly:** governance before retrieval follows the same idea. It is kept small here so the routing logic has something real to guard |

What is new here, and shown by the script below:

1. a SQL / RAG / BOTH classifier where every route carries a cited reason ID;
2. a per-claim merge across sources that flags numeric disagreement
   (MERGE-NUM-01) instead of picking one silently;
3. a role-scoped SQL gateway: each role's view list is enforced by SQLite's
   authorizer, not only by the policy layer.

<!-- run: python scripts/show_differentiator.py -->
```text
sql  ROUTE-SQL-01  How many open tickets do we have?
rag  ROUTE-RAG-01  What is our return policy?
both ROUTE-BOTH-01 How many open tickets do we have and what is the escalation policy?
     CONFLICT flagged on: open tickets (sql 5 vs docs 10)
denied  SELECT * FROM v_ticket_backlog, employees -> SEC-SELECT-03: denied by database authorizer: ['employees']
denied  SELECT * FROM v_salaries -> SEC-SELECT-03: only published views may be queried, blocked: ['v_salaries']
```
<!-- /run -->

The router composes with text2sql: text2sql could be the SQL engine behind
the `sql` route.

## How it works

1. `classify.classify(question)` -> `{"route", "reason_id", "reason", ...}`
   (e.g. ROUTE-BOTH-01: quantity words + entity + policy signal).
2. `govern.check(role, kind, name)` for every target; denials raise
   `AccessDenied` citing POL-ACCESS-01/02 *before* any query runs.
3. SQL via `views.run_readonly(con, sql, allowed_views=ROLE_VIEWS[role])`:
   text allowlist (SEC-SELECT-01/02/03), then the strict view-aware
   authorizer in `router/authz.py` scoped to that role's views, then a
   `fetchmany` cap.
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
python3 -m pytest tests/ -q
python3 scripts/count_tests.py     # prints the real total
streamlit run demo/app.py          # thin demo (pip install streamlit)
```

<!-- run: python scripts/count_tests.py -->
```text
78 tests collected
```
<!-- /run -->

## Knowledge

- [knowledge/domain-notes.md](knowledge/domain-notes.md) -- the data-agent
  retrieval pattern, in my own words
- [knowledge/architecture.md](knowledge/architecture.md) -- Mermaid diagram

## Guardrails

- Governance before retrieval (POL-ACCESS-00/01/02); denials audited.
- Strict view-aware SQLite authorizer (`router/authz.py`, the shared
  portfolio template): a base table can be read only while SQLite expands one
  of the caller's allowed views. Naming a table directly is denied however
  it is written: comma joins, `(employees)`, `"employees"`, `JOIN (t)`.
  `sqlite_master`, `load_extension`, PRAGMA, ATTACH and writes are denied.
  `tests/test_authorizer_strict.py` runs every case with the text check
  switched off, so the authorizer alone is proven.
- Known residual: `SELECT count(*) FROM employees` reads no columns, so
  SQLite reports no column access to authorize; it can reveal a row count
  (never values). The text check blocks the plain form.
- `fetchmany(ROW_CAP+1)` cap; no `fetchall()` on planner paths.
- Hash-chained audit log; `audit.verify()` detects tampering.
- Conflicts surfaced (MERGE-NUM-01), never silently resolved.

## Limitations and known failures

- Fixed per-view SQL templates, not full text-to-SQL (routing is the focus).
- Rule-based classifier: regression checks, not a quality claim; odd
  phrasings fall back to RAG (ROUTE-RAG-02).
- TF-IDF retrieval; fine for 10 docs, not for 10M.
- `role` is caller-supplied; production needs real authN (OIDC).
- In-memory SQLite; no persistence.

## Built / Written-not-run / Planned

| Status | Item |
|---|---|
| Built | Classifier (SQL/RAG/BOTH + cited reasons), governance, merge with conflict flags, hardened gateway, TF-IDF RAG, hash-chained audit, demo, tests (count above) |
| Written-not-run | Streamlit demo (needs `pip install streamlit`; logic fully tested in `demo_helpers`) |
| Planned | LLM synthesis over cited claims; OIDC roles; async retrieval with latency budgets |

## Standardization review (2026-10-18)

Bugs found in review and fixed, each with a regression test in
`tests/test_router.py` (section "review fixes"):

| ID | Bug | Fix |
|---|---|---|
| SEC-AUTHZ-01 | The README described a strict authorizer, but the gateway used a text-based table check. `SELECT * FROM v_ticket_backlog, employees` returned all 15 salary rows; `(employees)` and `"employees"` also leaked | Shared strict view-aware authorizer; the text check stays as a first layer |
| SEC-ROLE-01 | The gateway allowed every view to every caller; only the policy layer knew about roles | `run_readonly(..., allowed_views=ROLE_VIEWS[role])` |
| TEST-PATH-01 | Tests read the docs from one developer's absolute path, so 4 tests failed on any other machine | Path relative to the repo |
| RAG-RANK-01 | Question words ("what", "policy") drove ranking, so "What is our return policy?" returned the wrong SOP; titles and headings were not indexed | Stopwords, plural folding, title and section indexed |
| RAG-CHUNK-01 | The `# Title` line was indexed as its own empty chunk | Title lines are attached to the document, not chunked |
| MERGE-REV-01 | Total revenue counted cancelled orders (5,233.58) | Cancelled orders excluded (4,773.60); per-status counts added |

Wording: the domain notes were rewritten in my own words with no
attribution to outside material; two "fictional" company names in the seed
data turned out to belong to real businesses and were replaced with
invented ones (now Calvessa Goods and Brisquel Cafe). ADR: [docs/adr/0001-strict-gateway.md](docs/adr/0001-strict-gateway.md).

## Related repos

- `Jagadish-text2sql-data-agent` -- the single-source NL-to-SQL layer this
  router sits above (composes: router -> text2sql as SQL engine).
- `Jagadish-governed-data-agent` -- the deny-first governance pattern the
  router's policy layer follows.
- `Jagadish-agent-feedback-loop` -- closing the loop on retrieved answers.
