# Interview points

## The one-liner
"A data agent that routes one question across SQL and documents, enforces
role-based access *before* touching any source, and merges answers with
per-claim citations -- flagging conflicts instead of silently picking."

## Why routing matters
Most demos wire a single retrieval path. Real enterprise questions span
structured and unstructured data ("how many tickets, and what's the
escalation policy?"). Somebody has to decide which sources to consult, and
that decision needs to be explainable and audited -- not buried in a prompt.

## Design decisions to defend
- **Rule-based classifier, not an LLM.** Routing determinism is the point:
  52 tests pin every route. An LLM deciding what to look at is a black box
  at the worst possible layer.
- **Governance before retrieval.** `govern.check` runs before any query.
  Checking after retrieval means the data was already read -- the audit log
  would record a violation, not prevent one.
- **Strict view-aware authorizer.** The SQLite authorizer allows backing
  tables only when not explicitly named in the query, so
  `SELECT * FROM tickets, v_ticket_backlog` is denied even with the text
  check disabled (tested). Text allowlist is the first layer, the
  authorizer the backstop.
- **Conflicts surfaced, not resolved silently.** MERGE-NUM-01: the database
  wins numeric disagreements, but both values and both citations stay in
  the output.

## Numbers to quote (all from real runs)
- 52 tests, all green, stdlib only.
- Live demo: "How many open tickets..." -> SQL says 5, docs say ~10;
  the router flags CONFLICT and cites both.
- Governance: `analyst` asking for average salary -> denied with
  POL-ACCESS-01, audited.

## Honest limitations
- Fixed per-view SQL templates, not full text-to-SQL (routing is the
  focus; see text2sql-data-agent for the NL-to-SQL layer).
- TF-IDF retrieval, no embeddings -- fine for 10 docs, not for 10M.
- In-memory SQLite; no persistence, no multi-tenancy.
