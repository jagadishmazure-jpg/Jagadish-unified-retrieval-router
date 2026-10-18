"""Hash-chained audit log of every routing decision.

Each record commits to the previous hash, so tampering with any entry
breaks verification of everything after it.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone


def new_log() -> dict:
    return {"head": "GENESIS", "entries": []}


def record(log: dict, entry: dict) -> dict:
    body = json.dumps(entry, sort_keys=True, default=str)
    digest = hashlib.sha256((log["head"] + body).encode()).hexdigest()
    rec = {
        "prev": log["head"],
        "hash": digest,
        "ts": datetime.now(timezone.utc).isoformat(),
        "entry": entry,
    }
    log["entries"].append(rec)
    log["head"] = digest
    return rec


def verify(log: dict) -> bool:
    prev = "GENESIS"
    for rec in log["entries"]:
        body = json.dumps(rec["entry"], sort_keys=True, default=str)
        if rec["prev"] != prev:
            return False
        if hashlib.sha256((prev + body).encode()).hexdigest() != rec["hash"]:
            return False
        prev = rec["hash"]
    return prev == log["head"]
