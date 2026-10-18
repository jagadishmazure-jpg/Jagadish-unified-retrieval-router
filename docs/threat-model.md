# Threat model (STRIDE-lite)

## Assets
- Structured data (orders, inventory, tickets, salaries)
- Unstructured corpus (SOPs, email threads)
- Routing decisions + audit log

## Threats & mitigations

| # | Threat | Mitigation |
|---|--------|------------|
| T1 | SQL injection via question text | Fixed per-view templates only; gateway text checks (SEC-SELECT-01/02/03); strict view-aware authorizer backstop |
| T2 | Unauthorized data access (e.g. analyst reading salaries) | `govern.check` before any source access; denials cite policy IDs; audited |
| T3 | Retrieval of restricted email threads | Doc-set policies (POL-ACCESS-02); RAG `allowed_sets` filter |
| T4 | Audit log tampering | Hash chain; `audit.verify()` detects edits |
| T5 | Silent wrong answers from source conflicts | MERGE-NUM-01: conflicts flagged with both values and citations |
| T6 | Denial of service via huge result sets | `fetchmany(ROW_CAP+1)` cap; no `fetchall()` on planner path |
| T7 | Prompt injection via document text | Documents are retrieved, not executed; no LLM in this repo to inject into |

## Residual risks
- The `role` parameter is caller-supplied (no authN). Production needs OIDC.
- TF-IDF has no access-control at the chunk level beyond doc sets.
- In-memory DB: no persistence, no backup story.
