"""Tests for the unified retrieval router (deterministic, no network)."""

import sqlite3

import pytest

from router import audit, classify, corpus, govern, merge, rag, seed, views
from router import demo_helpers, router
from router.views import GatewayError

DOCS = "/home/hatch/workspace/github-scaffolds/Jagadish-unified-retrieval-router/docs"


@pytest.fixture()
def con():
    c = seed.seed_db()
    views.create_views(c)
    return c


@pytest.fixture()
def index():
    return rag.build_index(corpus.load_corpus(DOCS))


@pytest.fixture()
def log():
    return audit.new_log()


# ---- seed ---------------------------------------------------------------
def test_seed_row_counts(con):
    assert con.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 6
    assert con.execute("SELECT COUNT(*) FROM inventory").fetchone()[0] == 5
    assert con.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 7
    assert con.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 3


def test_open_ticket_count(con):
    n = con.execute("SELECT COUNT(*) FROM tickets WHERE status='open'").fetchone()[0]
    assert n == 5


def test_low_stock_skus(con):
    rows = con.execute(
        "SELECT sku FROM inventory WHERE on_hand < reorder_point ORDER BY sku"
    ).fetchall()
    assert [r[0] for r in rows] == ["SKU-102", "SKU-104"]


# ---- classify -----------------------------------------------------------
def test_classify_sql_how_many_tickets():
    d = classify.classify("How many open tickets do we have?")
    assert d["route"] == "sql"
    assert d["reason_id"] == "ROUTE-SQL-01"
    assert d["sql_views"] == ["v_ticket_backlog"]


def test_classify_sql_revenue():
    d = classify.classify("What is the total revenue?")
    assert d["route"] == "sql"
    assert "v_order_summary" in d["sql_views"]


def test_classify_sql_inventory():
    d = classify.classify("List SKUs below reorder point")
    assert d["route"] == "sql"
    assert d["sql_views"] == ["v_inventory_status"]


def test_classify_rag_policy():
    d = classify.classify("What is our return policy?")
    assert d["route"] == "rag"
    assert d["reason_id"] == "ROUTE-RAG-01"
    assert d["doc_sets"] == ["sops"]


def test_classify_rag_email():
    d = classify.classify("What did the supplier say about the delay?")
    assert d["route"] == "rag"
    assert "emails" in d["doc_sets"]


def test_classify_both():
    d = classify.classify(
        "How many open tickets do we have and what is the escalation policy?"
    )
    assert d["route"] == "both"
    assert d["reason_id"] == "ROUTE-BOTH-01"
    assert d["sql_views"] == ["v_ticket_backlog"]
    assert "sops" in d["doc_sets"]


def test_classify_reason_cited():
    d = classify.classify("How many orders shipped?")
    assert d["reason_id"].startswith("ROUTE-")
    assert d["reason"]  # non-empty human reason


def test_classify_default_rag():
    d = classify.classify("Tell me something interesting")
    assert d["route"] == "rag"
    assert d["reason_id"] == "ROUTE-RAG-02"


def test_classify_salary_entity():
    d = classify.classify("What is the average salary?")
    assert d["route"] == "sql"
    assert d["sql_views"] == ["v_salaries"]


def test_classify_entity_no_signal_defaults_sql():
    d = classify.classify("tickets")
    assert d["route"] == "sql"
    assert d["reason_id"] == "ROUTE-SQL-02"


# ---- govern -------------------------------------------------------------
def test_analyst_salaries_denied():
    with pytest.raises(govern.AccessDenied) as ei:
        govern.check("analyst", "view", "v_salaries")
    assert ei.value.policy_id == "POL-ACCESS-01"


def test_analyst_emails_denied():
    with pytest.raises(govern.AccessDenied) as ei:
        govern.check("analyst", "docset", "emails")
    assert ei.value.policy_id == "POL-ACCESS-02"


def test_hr_admin_salaries_allowed():
    govern.check("hr_admin", "view", "v_salaries")  # no raise


def test_support_lead_emails_allowed():
    govern.check("support_lead", "docset", "emails")  # no raise


def test_unknown_role_denied():
    with pytest.raises(govern.AccessDenied) as ei:
        govern.check("intruder", "view", "v_order_summary")
    assert ei.value.policy_id == "POL-ACCESS-00"


def test_denied_carries_policy_id():
    try:
        govern.check("support_lead", "view", "v_salaries")
    except govern.AccessDenied as e:
        assert "POL-ACCESS-01" in str(e)
    else:
        pytest.fail("expected AccessDenied")


# ---- gateway ------------------------------------------------------------
def test_gateway_rejects_insert(con):
    with pytest.raises(GatewayError, match="SEC-SELECT-01"):
        views.run_readonly(con, "INSERT INTO orders VALUES('x','x','x',1,1.0,'shipped','2026-10-01')")


def test_gateway_rejects_raw_table(con):
    with pytest.raises(GatewayError, match="SEC-SELECT-03"):
        views.run_readonly(con, "SELECT * FROM orders")


def test_gateway_allows_view(con):
    cols, rows, truncated = views.run_readonly(con, "SELECT * FROM v_ticket_backlog")
    assert len(rows) == 5
    assert not truncated
    assert "ticket_id" in cols


def test_gateway_caps_at_fetch_time(con, monkeypatch):
    con.execute(
        "CREATE VIEW v_big AS SELECT t.ticket_id FROM tickets t, inventory i, orders o"
    )
    monkeypatch.setattr(views, "ALLOWED_VIEWS", views.ALLOWED_VIEWS | {"v_big"})
    monkeypatch.setattr(
        views, "VIEW_BACKING",
        {**views.VIEW_BACKING, "v_big": {"tickets", "inventory", "orders"}},
    )
    cols, rows, truncated = views.run_readonly(con, "SELECT * FROM v_big")
    assert len(rows) == views.ROW_CAP
    assert truncated


def test_gateway_caps_limit_comment_bypass(con, monkeypatch):
    con.execute(
        "CREATE VIEW v_big2 AS SELECT t.ticket_id FROM tickets t, inventory i, orders o"
    )
    monkeypatch.setattr(views, "ALLOWED_VIEWS", views.ALLOWED_VIEWS | {"v_big2"})
    monkeypatch.setattr(
        views, "VIEW_BACKING",
        {**views.VIEW_BACKING, "v_big2": {"tickets", "inventory", "orders"}},
    )
    cols, rows, truncated = views.run_readonly(con, "SELECT * FROM v_big2 LIMIT 100000 -- x")
    assert len(rows) == views.ROW_CAP
    assert truncated


def test_authorizer_denies_comma_join_without_text_check(con):
    # New standing rule: test the authorizer with the text check disabled.
    sql = "SELECT * FROM tickets, v_ticket_backlog"
    with views.views_only(con, sql):
        with pytest.raises(sqlite3.DatabaseError):
            con.execute(sql).fetchall()


def test_authorizer_denies_quoted_sqlite_master_without_text_check(con):
    sql = 'SELECT name FROM "sqlite_master"'
    with views.views_only(con, sql):
        with pytest.raises(sqlite3.DatabaseError):
            con.execute(sql).fetchall()


def test_authorizer_allows_view_expansion(con):
    sql = "SELECT * FROM v_ticket_backlog"
    with views.views_only(con, sql):
        rows = con.execute(sql).fetchall()
    assert len(rows) == 5


def test_authorizer_cleared_on_exit(con):
    sql = "SELECT * FROM v_ticket_backlog"
    with views.views_only(con, sql):
        pass
    # DDL works again once the authorizer is cleared
    con.execute("CREATE TABLE t_tmp(x INTEGER)")
    con.execute("DROP TABLE t_tmp")


# ---- rag ---------------------------------------------------------------
def test_rag_citation_format(index):
    hits = rag.search(index, "return policy")
    assert hits
    assert "§" in hits[0]["citation"]
    assert hits[0]["citation"].endswith(hits[0]["section"])


def test_rag_finds_policy(index):
    hits = rag.search(index, "return policy eligibility")
    assert hits[0]["doc"] == "returns-policy.md"


def test_rag_not_found(index):
    assert rag.search(index, "zxqv kwyjblorp") == []


def test_rag_respects_allowed_sets(index):
    hits = rag.search(index, "supplier delay shipment", allowed_sets={"sops"})
    assert all(h["doc"].endswith(".md") and "email" not in h["doc"] for h in hits)


def test_rag_top_k(index):
    hits = rag.search(index, "policy", top_k=2)
    assert len(hits) <= 2


# ---- merge --------------------------------------------------------------
def _claims():
    sql_claims = [
        {"subject": "open tickets", "value": "5", "kind": "number",
         "citation": "sql:v_ticket_backlog"}
    ]
    rag_claims = [
        {"subject": "Current volume",
         "value": "Current open ticket volume is approximately 10 across all queues.",
         "kind": "fact", "citation": "support-escalation.md §Current volume"}
    ]
    return sql_claims, rag_claims


def test_merge_conflict_flagged():
    sql_claims, rag_claims = _claims()
    conflicts = merge.find_conflicts(sql_claims, rag_claims)
    assert len(conflicts) == 1
    assert conflicts[0]["flagged"] is True
    assert conflicts[0]["sql_value"] == "5"
    assert conflicts[0]["rag_value"] == "10"


def test_merge_prefers_sql_for_numbers():
    sql_claims, rag_claims = _claims()
    conflicts = merge.find_conflicts(sql_claims, rag_claims)
    assert "MERGE-NUM-01" in conflicts[0]["resolution"]


def test_merge_citations_present():
    sql_claims, rag_claims = _claims()
    text = merge.render(sql_claims + rag_claims, merge.find_conflicts(sql_claims, rag_claims))
    assert "sql:v_ticket_backlog" in text
    assert "support-escalation.md" in text


def test_merge_no_conflict_when_agree():
    sql_claims = [
        {"subject": "open tickets", "value": "5", "kind": "number",
         "citation": "sql:v_ticket_backlog"}
    ]
    rag_claims = [
        {"subject": "note", "value": "We have 5 open tickets right now.",
         "kind": "fact", "citation": "doc §x"}
    ]
    assert merge.find_conflicts(sql_claims, rag_claims) == []


def test_merge_fact_claims_kept():
    chunks = [{"section": "Eligibility", "text": "Returns within 30 days.",
               "citation": "returns-policy.md §Eligibility"}]
    claims = merge.to_rag_claims(chunks)
    assert claims[0]["citation"] == "returns-policy.md §Eligibility"


def test_render_conflict_text():
    sql_claims, rag_claims = _claims()
    conflicts = merge.find_conflicts(sql_claims, rag_claims)
    text = merge.render(sql_claims + rag_claims, conflicts)
    assert "CONFLICT" in text


# ---- audit --------------------------------------------------------------
def test_audit_chain_verifies(log):
    audit.record(log, {"q": "a"})
    audit.record(log, {"q": "b"})
    assert audit.verify(log) is True


def test_audit_tamper_detected(log):
    audit.record(log, {"q": "a"})
    log["entries"][0]["entry"]["q"] = "tampered"
    assert audit.verify(log) is False


def test_audit_records_routing_fields(log):
    rec = audit.record(log, {"question": "q", "route": "both", "reason_id": "ROUTE-BOTH-01"})
    assert rec["entry"]["reason_id"] == "ROUTE-BOTH-01"
    assert "ts" in rec


# ---- router end-to-end --------------------------------------------------
def test_router_sql_only(con, index, log):
    res = router.answer("How many open tickets do we have?", role="analyst",
                        con=con, corpus_index=index, log=log)
    assert res["route"] == "sql"
    assert any(c["subject"] == "open tickets" and c["value"] == "5" for c in res["claims"])
    assert "[sql:v_ticket_backlog]" in res["answer"]


def test_router_rag_only(con, index, log):
    res = router.answer("What is our return policy?", role="analyst",
                        con=con, corpus_index=index, log=log)
    assert res["route"] == "rag"
    assert "returns-policy.md" in res["answer"]


def test_router_both_flags_conflict(con, index, log):
    res = router.answer(
        "How many open tickets do we have and what is the escalation policy?",
        role="support_lead", con=con, corpus_index=index, log=log)
    assert res["route"] == "both"
    assert len(res["conflicts"]) == 1
    assert "CONFLICT" in res["answer"]


def test_router_denied_salary(con, index, log):
    with pytest.raises(govern.AccessDenied) as ei:
        router.answer("What is the average salary?", role="analyst",
                      con=con, corpus_index=index, log=log)
    assert ei.value.policy_id == "POL-ACCESS-01"
    assert log["entries"][-1]["entry"]["outcome"] == "denied"


def test_router_denied_emails(con, index, log):
    with pytest.raises(govern.AccessDenied) as ei:
        router.answer("What did the supplier say about the delay?", role="analyst",
                      con=con, corpus_index=index, log=log)
    assert ei.value.policy_id == "POL-ACCESS-02"


def test_router_audit_logged(con, index, log):
    router.answer("How many open tickets do we have?", role="analyst",
                  con=con, corpus_index=index, log=log)
    entry = log["entries"][-1]["entry"]
    assert entry["route"] == "sql"
    assert entry["reason_id"] == "ROUTE-SQL-01"
    assert entry["outcome"] == "answered"


def test_router_hr_admin_salary_ok(con, index, log):
    res = router.answer("What is the average salary?", role="hr_admin",
                        con=con, corpus_index=index, log=log)
    assert res["route"] == "sql"
    assert any(c["subject"] == "average salary" for c in res["claims"])


def test_router_views_created(con):
    names = {r[0] for r in
             con.execute("SELECT name FROM sqlite_master WHERE type='view'").fetchall()}
    assert {"v_order_summary", "v_inventory_status", "v_ticket_backlog", "v_salaries"} <= names


# ---- demo helpers -------------------------------------------------------
def test_sample_questions_nonempty():
    qs = demo_helpers.sample_questions()
    assert len(qs) == 6
    assert all(isinstance(q, str) and isinstance(r, str) for q, r in qs)


def test_format_answer_contains_route():
    res = {"route": "both", "reason_id": "ROUTE-BOTH-01",
           "reason": "why", "answer": "the answer"}
    text = demo_helpers.format_answer(res)
    assert "both" in text and "ROUTE-BOTH-01" in text
