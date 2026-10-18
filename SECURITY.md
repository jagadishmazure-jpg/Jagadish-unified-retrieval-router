# Security policy

## Scope
This is a synthetic-data demo. It runs offline on in-memory SQLite with a
deterministic rule-based router; there is no network access, no real data,
and no deployment.

## Controls in the code
- SELECT-only SQL gateway: text allowlist (SEC-SELECT-01/02/03) plus a
  strict view-aware SQLite authorizer backstop; `fetchmany` row cap.
- Role-based source policies (POL-ACCESS-00/01/02) enforced before any
  retrieval; denials are audited with the policy ID.
- Hash-chained audit log; tampering is detectable via `audit.verify()`.

## Reporting
If you find a security issue in this demo, please open a GitHub issue.
Do not include any real credentials or data in reports.
