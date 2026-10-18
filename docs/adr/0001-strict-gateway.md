# ADR 0001: Strict, role-scoped SQL gateway

- Status: accepted (2026-10-18, standardization review)

## Context

The gateway checked table names in the SQL text against a list of views.
The README already described a "strict view-aware authorizer", but the code
did not have one. In review, `SELECT * FROM v_ticket_backlog, employees`
passed the text check and returned the salary table. Parenthesised and
quoted names leaked the same way. The gateway also accepted every view from
every role; only the policy layer above it knew about roles.

## Decision

- Use the portfolio's shared authorizer (`router/authz.py`). A base table is
  readable only while SQLite expands one of the allowed views.
- Pass the caller's role views into `run_readonly`, so the database enforces
  the same scope as the policy layer.
- Keep the text check as a first layer with clear error IDs, and prove the
  authorizer alone in `tests/test_authorizer_strict.py` with the text check
  off.

## Consequences

- Every bypass form tried in review is denied by SQLite.
- Residual: a column-free `count(*)` on a base table can reveal a row count.
  The text check blocks the plain form; values are never exposed.
