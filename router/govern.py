"""Role-based access policies enforced at routing time.

A denied route raises AccessDenied carrying the policy ID, so the caller
(and the audit log) cites exactly which policy blocked it. Denials happen
BEFORE any source is touched.
"""

from __future__ import annotations

ROLE_VIEWS = {
    "analyst": {"v_order_summary", "v_inventory_status", "v_ticket_backlog"},
    "support_lead": {"v_order_summary", "v_inventory_status", "v_ticket_backlog"},
    "hr_admin": {
        "v_order_summary", "v_inventory_status", "v_ticket_backlog", "v_salaries",
    },
}

ROLE_DOCSETS = {
    "analyst": {"sops"},
    "support_lead": {"sops", "emails"},
    "hr_admin": {"sops"},
}

POLICIES = {
    "POL-ACCESS-00": "unknown role: no access at all",
    "POL-ACCESS-01": "salary data (v_salaries) is restricted to the hr_admin role",
    "POL-ACCESS-02": "email threads are restricted to the support_lead role",
}


class AccessDenied(Exception):
    def __init__(self, policy_id: str, detail: str):
        super().__init__(f"{policy_id}: {detail}")
        self.policy_id = policy_id
        self.detail = detail


def check(role: str, kind: str, name: str) -> None:
    """Raise AccessDenied if ``role`` may not use ``name`` (view or docset)."""
    if role not in ROLE_VIEWS:
        raise AccessDenied("POL-ACCESS-00", f"unknown role '{role}'")
    if kind == "view":
        allowed, policy = ROLE_VIEWS[role], "POL-ACCESS-01"
    elif kind == "docset":
        allowed, policy = ROLE_DOCSETS[role], "POL-ACCESS-02"
    else:
        raise ValueError(f"unknown kind '{kind}'")
    if name not in allowed:
        raise AccessDenied(
            policy,
            f"role '{role}' may not access {kind} '{name}': {POLICIES[policy]}",
        )
