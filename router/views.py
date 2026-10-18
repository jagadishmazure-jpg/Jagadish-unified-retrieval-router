"""Read-only SQL views + SELECT-only gateway.

Two layers (defense in depth):
  1. Text checks (SEC-SELECT-01/02/03): SELECT-only, no write keywords,
     only published views after FROM/JOIN (parentheses and quotes seen through).
  2. Strict view-aware SQLite authorizer (``router/authz.py``): a base-table
     READ is allowed only when SQLite reports it on behalf of an allowed view
     (the authorizer's view-name argument). A direct read, e.g. the
     ``employees`` side of ``SELECT * FROM v_ticket_backlog, employees``, is
     denied whatever the text check saw. sqlite_master, writes, PRAGMA and
     load_extension are always denied.

The gateway is role-scoped: callers pass the views the role may read
(``govern.ROLE_VIEWS``), so even a query that only names allowed views can
not reach salary rows unless the role holds ``v_salaries``.

Row cap: ``fetchmany(ROW_CAP + 1)``; no LIMIT rewriting, no ``fetchall()``
on planner queries.
"""

from __future__ import annotations

import re
import sqlite3

from . import authz

ROW_CAP = 100

ALLOWED_VIEWS = {"v_order_summary", "v_inventory_status", "v_ticket_backlog", "v_salaries"}


class GatewayError(Exception):
    pass


def create_views(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    cur.execute(
        "CREATE VIEW IF NOT EXISTS v_order_summary AS "
        "SELECT status, COUNT(*) AS n, ROUND(SUM(amount),2) AS revenue "
        "FROM orders GROUP BY status"
    )
    cur.execute(
        "CREATE VIEW IF NOT EXISTS v_inventory_status AS "
        "SELECT sku, product, warehouse, on_hand, reorder_point, "
        "CASE WHEN on_hand < reorder_point THEN 'low' ELSE 'ok' END AS flag "
        "FROM inventory"
    )
    cur.execute(
        "CREATE VIEW IF NOT EXISTS v_ticket_backlog AS "
        "SELECT ticket_id, customer, priority, category, status "
        "FROM tickets WHERE status='open'"
    )
    cur.execute(
        "CREATE VIEW IF NOT EXISTS v_salaries AS "
        "SELECT emp_id, name, dept, salary FROM employees"
    )
    con.commit()


_WRITE_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|grant|revoke)\b",
    re.IGNORECASE,
)
_FROM_JOIN_RE = re.compile(
    r"\b(?:from|join)\b\s*\(*\s*[`\"\[]?([A-Za-z_]\w*)[`\"\]]?", re.IGNORECASE
)
_NOT_TABLES = {"select", "with", "values"}


def _strip_literals(sql: str) -> str:
    return re.sub(r"'[^']*'", "''", sql)


def _referenced_tables(sql: str) -> set[str]:
    """Table names explicitly named after FROM/JOIN (comments cut first)."""
    cleaned = _strip_literals(sql)
    cleaned = re.sub(r"/\*.*?\*/", " ", cleaned)
    cleaned = re.sub(r"--.*", " ", cleaned)
    return {m.group(1).lower() for m in _FROM_JOIN_RE.finditer(cleaned)} - _NOT_TABLES


def run_readonly(con: sqlite3.Connection, sql: str, allowed_views=None):
    """Run a planner query. Returns (columns, rows, truncated).

    ``allowed_views`` narrows the published views for this call (the role's
    views); default is every published view.
    """
    allowed = set(ALLOWED_VIEWS) if allowed_views is None else set(allowed_views) & ALLOWED_VIEWS
    stripped = sql.strip()
    if not re.match(r"(?i)^select\b", stripped):
        raise GatewayError("SEC-SELECT-01: only SELECT statements are allowed")
    if _WRITE_RE.search(_strip_literals(stripped)):
        raise GatewayError("SEC-SELECT-02: write/DDL keyword detected")
    tables = _referenced_tables(stripped)
    bad = {t for t in tables if t not in allowed}
    if bad:
        raise GatewayError(
            f"SEC-SELECT-03: only published views may be queried, blocked: {sorted(bad)}"
        )
    with authz.views_only(con, allowed) as denied:
        try:
            cur = con.execute(stripped)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchmany(ROW_CAP + 1)
        except sqlite3.DatabaseError as e:
            if denied:
                raise GatewayError(
                    f"SEC-SELECT-03: denied by database authorizer: {sorted(set(denied))}"
                ) from None
            raise GatewayError(f"SEC-SELECT-01: query failed ({e})") from None
    truncated = len(rows) > ROW_CAP
    return cols, rows[:ROW_CAP], truncated
