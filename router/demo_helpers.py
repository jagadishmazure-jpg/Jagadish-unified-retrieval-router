"""Demo helpers: sample questions and answer formatting (fully tested)."""

from __future__ import annotations


def sample_questions() -> list[tuple[str, str]]:
    """(question, role) pairs exercising every route and one denial."""
    return [
        ("How many open tickets do we have?", "analyst"),
        ("What is our return policy?", "analyst"),
        (
            "How many open tickets do we have and what is the escalation policy?",
            "support_lead",
        ),
        ("Which SKUs are below reorder point?", "analyst"),
        ("What did the supplier say about the delay?", "support_lead"),
        ("What is the average salary?", "analyst"),  # denied by POL-ACCESS-01
    ]


def format_answer(result: dict) -> str:
    lines = [
        f"**Route:** {result['route']} ({result['reason_id']})",
        f"**Why:** {result['reason']}",
        "",
        result["answer"],
    ]
    return "\n".join(lines)
