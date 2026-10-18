"""Synthetic structured data for the fictional Harborline Goods.

Deterministic: fixed rows, no randomness. Backs the router's SQL path.
"""

from __future__ import annotations

import sqlite3


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    return con


def seed(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    cur.execute(
        "CREATE TABLE orders(order_id TEXT PRIMARY KEY, customer TEXT, product TEXT,"
        " qty INTEGER, amount REAL, status TEXT, order_date TEXT)"
    )
    cur.execute(
        "CREATE TABLE inventory(sku TEXT PRIMARY KEY, product TEXT, warehouse TEXT,"
        " on_hand INTEGER, reorder_point INTEGER)"
    )
    cur.execute(
        "CREATE TABLE tickets(ticket_id TEXT PRIMARY KEY, customer TEXT, priority TEXT,"
        " category TEXT, status TEXT, created TEXT)"
    )
    cur.execute(
        "CREATE TABLE employees(emp_id TEXT PRIMARY KEY, name TEXT, dept TEXT, salary REAL)"
    )
    cur.executemany(
        "INSERT INTO orders VALUES(?,?,?,?,?,?,?)",
        [
            ("ORD-001", "Emberpine Outfitters", "Trail Backpack", 10, 899.90, "shipped", "2026-10-01"),
            ("ORD-002", "Cinder & Co.", "Camp Stove", 5, 749.75, "shipped", "2026-10-03"),
            ("ORD-003", "Northloop Books", "Desk Lamp", 20, 1199.60, "pending", "2026-10-05"),
            ("ORD-004", "Palefire Cafe", "Espresso Kit", 2, 459.98, "cancelled", "2026-10-06"),
            ("ORD-005", "Quill & Bolt", "Notebook Set", 50, 1249.50, "shipped", "2026-10-08"),
            ("ORD-006", "Sablewood Studio", "Canvas Pack", 15, 674.85, "pending", "2026-10-10"),
        ],
    )
    cur.executemany(
        "INSERT INTO inventory VALUES(?,?,?,?,?)",
        [
            ("SKU-101", "Trail Backpack", "WH-EAST", 120, 50),
            ("SKU-102", "Camp Stove", "WH-EAST", 18, 25),
            ("SKU-103", "Desk Lamp", "WH-WEST", 200, 40),
            ("SKU-104", "Espresso Kit", "WH-WEST", 8, 10),
            ("SKU-105", "Notebook Set", "WH-EAST", 300, 60),
        ],
    )
    cur.executemany(
        "INSERT INTO tickets VALUES(?,?,?,?,?,?)",
        [
            ("TKT-01", "Emberpine Outfitters", "P1", "shipping", "open", "2026-10-12"),
            ("TKT-02", "Cinder & Co.", "P2", "returns", "open", "2026-10-13"),
            ("TKT-03", "Northloop Books", "P3", "billing", "open", "2026-10-14"),
            ("TKT-04", "Palefire Cafe", "P2", "product", "open", "2026-10-15"),
            ("TKT-05", "Quill & Bolt", "P3", "shipping", "closed", "2026-10-09"),
            ("TKT-06", "Sablewood Studio", "P1", "product", "closed", "2026-10-07"),
            ("TKT-07", "Emberpine Outfitters", "P2", "returns", "open", "2026-10-16"),
        ],
    )
    cur.executemany(
        "INSERT INTO employees VALUES(?,?,?,?)",
        [
            ("EMP-01", "Dana Reyes", "Engineering", 145000.0),
            ("EMP-02", "Sam Okafor", "Support", 92000.0),
            ("EMP-03", "Priya Nair", "Finance", 138000.0),
        ],
    )
    con.commit()


def seed_db() -> sqlite3.Connection:
    con = connect()
    seed(con)
    return con
