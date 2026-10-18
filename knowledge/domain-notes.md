# Knowledge: the data-agent retrieval pattern

These notes describe the "data agent" pattern as this repo implements it:
one entry point that decides whether a question needs the database, the
documents, or both, and checks access before touching either. The wording
and examples are original to this repo.

## The problem

Enterprise questions rarely live in one place. "How many open tickets do we
have, and what is the escalation policy?" needs a number from the ticketing
database *and* prose from the support handbook. Most agent demos wire one
retrieval path (usually text-to-SQL *or* RAG) and leave the routing decision
implicit -- often to an LLM prompt with no audit trail.

## The pattern: route, govern, merge

1. **Classify the question.** Decide up front whether it needs structured
   data (SQL), unstructured data (documents), or both. The decision must be
   explainable: every route carries a cited reason (e.g. ROUTE-BOTH-01),
   not just a label.
2. **Govern at routing time.** Before touching any source, check the
   caller's role against per-source policies. A denied route raises with the
   policy ID cited (POL-ACCESS-01/02) and the denial is audited. Governance
   after retrieval is too late -- the data has already been read.
3. **Merge with citations, flag conflicts.** When both sources answer,
   attach a source citation to every claim. If the sources disagree on a
   number, prefer the structured source (databases beat prose for counts)
   but surface the conflict explicitly. Never silently pick one.

## Why rule-based routing here

An LLM classifier would be non-deterministic and harder to audit. For the
routing decision itself -- which sources to consult -- a small rule set over
question features (quantity words, named entities, policy language) is
faster, testable, and fully explainable. The LLM (in a real deployment)
belongs *after* routing, synthesizing the cited claims -- not before it,
deciding what to look at.

## What this repo demonstrates

- `router/classify.py`: ROUTE-SQL-01/02, ROUTE-RAG-01/02, ROUTE-BOTH-01
- `router/govern.py`: POL-ACCESS-00/01/02, checked before execution
- `router/merge.py`: MERGE-NUM-01 (structured wins numbers, conflict flagged)
- `router/views.py` + `router/authz.py`: role-scoped strict view-aware authorizer + fetchmany cap
- `router/audit.py`: hash-chained log of every routing decision
