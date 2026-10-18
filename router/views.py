"""Read-only SQL views + SELECT-only gateway.

Two layers (defense in depth):
  1. Text checks (SEC-SELECT-01/02/03): SELECT-only, no write keywords,
     only published views in FROM/JOIN.
  2. Strict view-aware SQLite authorizer (``views_only``): allows READ on
     views, and on a backing table ONLY when that table was not explicitly
     named in the query -- i.e. reads that come through view expansion.
     Denies sqlite_master, writes, DDL, PRAGMA, ATTACH. A comma join like
     ``SELECT * FROM tickets, v_ticket_backlog`` is denied even with the
     text check disabled, because ``tickets`` was explicitly named.

Row cap: ``fetchmany(ROW_CAP + 1)``; no LIMIT rewriting, no ``fetchall()``
on planner queries.
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager

ROW_CAP = 100

ALLOWED_VIEWS = {"v_order_summary", "v_inventory_status", "v_ticket_backlog", "v_salaries"}

# Backing tables each view expands to. The authorizer needs these so views
# keep working (SQLite fires the authorizer on base tables inside view
# definitions), but a backing table explicitly named in the query is NOT
# granted -- that is what makes the authorizer view-aware rather than loose.
VIEW_BACKING = {
    "v_order_summary": {"orders"},
    "v_inventory_status": {"inventory"},
    "v_ticket_backlog": {"tickets"},
    "v_salaries": {"employees"},
}


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
_FROM_JOIN_RE = re.compile(r"\b(?:from|join)\b\s*[`\"'\[]?([\w]+)[`\"'\]]?", re.IGNORECASE)


def _strip_literals(sql: str) -> str:
    return re.sub(r"'[^']*'", "''", sql)


def _referenced_tables(sql: str) -> set[str]:
    """Table names explicitly named after FROM/JOIN (comments cut first)."""
    cleaned = _strip_literals(sql)
    cleaned = re.sub(r"/\*.*?\*/", " ", cleaned)
    cleaned = re.sub(r"--.*", " ", cleaned)
    return {m.group(1).lower() for m in _FROM_JOIN_RE.finditer(cleaned)}


@contextmanager
def views_only(con: sqlite3.Connection, sql: str):
    """Yield ``con`` with the strict view-aware authorizer for one query.

    ``readable`` = allowed views + backing tables that were NOT explicitly
    named in ``sql``. So ``SELECT * FROM v_ticket_backlog`` can read
    ``tickets`` via view expansion, but ``SELECT * FROM tickets`` (or
    ``..., v_ticket_backlog``) cannot read ``tickets`` at all.
    Denied access raises ``sqlite3.DatabaseError`` from the driver.
    The authorizer is always cleared on exit.
    """
    named = _referenced_tables(sql)
    readable = set(ALLOWED_VIEWS)
    for view in ALLOWED_VIEWS:
        for table in VIEW_BACKING.get(view, ()):
            if table not in named:
                readable.add(table)

    def _authorizer(action: int, arg1: str | None, arg2: str | None,
                    dbname: str | None, source: str | None) -> int:
        if action == sqlite3.SQLITE_SELECT:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_FUNCTION:
            # Aggregate/scalar functions (COUNT, ROUND, ...) cannot write;
            # table access is still gated by SQLITE_READ.
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_READ:
            name = (arg1 or "").lower()
            if name in readable:
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY
        # Deny everything else: writes, DDL, PRAGMA, ATTACH, ...
        return sqlite3.SQLITE_DENY

    con.set_authorizer(_authorizer)
    try:
        yield con
    finally:
        con.set_authorizer(None)


def run_readonly(con: sqlite3.Connection, sql: str):
    """Run a planner query. Returns (columns, rows, truncated)."""
    stripped = sql.strip()
    if not re.match(r"(?i)^select\b", stripped):
        raise GatewayError("SEC-SELECT-01: only SELECT statements are allowed")
    if _WRITE_RE.search(_strip_literals(stripped)):
        raise GatewayError("SEC-SELECT-02: write/DDL keyword detected")
    tables = _referenced_tables(stripped)
    bad = {t for t in tables if t not in ALLOWED_VIEWS}
    if bad:
        raise GatewayError(
            f"SEC-SELECT-03: only published views may be queried, blocked: {sorted(bad)}"
        )
    with views_only(con, stripped):
        try:
            cur = con.execute(stripped)
        except sqlite3.DatabaseError as e:
            raise GatewayError(f"SEC-SELECT-03: denied by authorizer backstop: {e}")
    cols = [d[0] for d in cur.description] if cur.description else []
    rows = cur.fetchmany(ROW_CAP + 1)
    truncated = len(rows) > ROW_CAP
    return cols, rows[:ROW_CAP], truncated
