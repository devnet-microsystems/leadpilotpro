import json
import sqlite3
import db_connector
import pytest
from fastapi.testclient import TestClient

from web_server import app, get_current_user

app.dependency_overrides[get_current_user] = lambda: {"username": "admin"}
client = TestClient(app)

def _seed_db(db_path):
    conn = db_connector.get_connection(db_path)
    # Seed product, ICP, research_campaign, queries
    conn.execute("INSERT INTO products (id, name, slug, status, raw_summary, created_at_utc, updated_at_utc) VALUES (1, 'Prod1', 'prod1', 'READY', '{}', 'now', 'now')")
    conn.execute("INSERT INTO products (id, name, slug, status, raw_summary, created_at_utc, updated_at_utc) VALUES (2, 'Prod2', 'prod2', 'READY', '{}', 'now', 'now')")
    conn.execute("INSERT INTO ideal_customer_profiles (id, name, roles, industries, company_sizes, countries, languages, created_at_utc) VALUES (1, 'ICP', '[]', '[]', '[]', '[]', '[]', 'now')")
    conn.execute("INSERT INTO research_campaigns (id, product_id, icp_id, name, created_at_utc) VALUES (1, 1, 1, 'C1', 'now')")
    conn.execute("INSERT INTO research_campaigns (id, product_id, icp_id, name, created_at_utc) VALUES (2, 2, 1, 'C2', 'now')")
    conn.execute("INSERT INTO campaign_queries (campaign_id, family, query, target_key, is_enabled) VALUES (1, 'DISCOVERY', 'query', 'CEO|SaaS|IT', 1)")
    
    # Seed prospect and sources
    conn.execute("INSERT INTO prospects (id, target_url, company_name, business_email, source_file, status, imported_at_utc, qualification_status) "
                 "VALUES (1, 'http://a.com', 'A', 'a@a.com', 'none', 'pending_review', 'now', 'REVIEW_REQUIRED')")
    # Add a second prospect for Prod2
    conn.execute("INSERT INTO prospects (id, target_url, company_name, business_email, source_file, status, imported_at_utc, qualification_status) "
                 "VALUES (2, 'http://b.com', 'B', 'b@b.com', 'none', 'pending_review', 'now', 'REVIEW_REQUIRED')")
    
    conn.execute("INSERT INTO query_runs (run_id, target_key, query, family, provider, raw_results, unique_domains) VALUES ('QR1', 'CEO|SaaS|IT', 'query', 'DISCOVERY', 'test', 1, 1)")
    conn.execute("INSERT INTO prospect_sources (prospect_id, source_type, discovered_at, query_run_id) VALUES (1, 'OSINT', 'now', 'QR1')")
    conn.execute("INSERT INTO prospect_sources (prospect_id, source_type, discovered_at, query_run_id) VALUES (2, 'OSINT', 'now', 'QR1')")
    
    # Associate prospect 2 with product 2 explicitly via a different query/campaign if we were being strict,
    # but the pipeline query relies on prospect_product_fit for rejected counts, so let's pre-reject prospect 2 for product 2.
    conn.execute("INSERT INTO prospect_product_fit (prospect_id, product_id, fit_status, reason) VALUES (2, 2, 'NO_FIT', 'Bad')")
    conn.execute("UPDATE prospects SET qualification_status = 'REJECTED' WHERE id = 2")
    
    conn.commit()
    conn.close()

def test_pipeline_status_no_parallel_state(fresh_db):
    _seed_db(fresh_db)
    res = client.get("/api/orchestrator/pipeline_status", params={"product_id": 1})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["discovered"] == 2  # Discovered counts all prospects from queries linked to prod 1. Wait, QR1 is linked to C1 (prod 1) and both prospects have QR1.
    assert data["qualified"] == 0
    assert data["rejected"] == 0 # Rejected count MUST be 0 for Prod 1, because Prospect 2 is rejected for Prod 2.
    assert data["approved"] == 0
    assert data["exported"] is None
    assert data["export_tracking"] == "not_available"

def test_evaluate_fit_is_idempotent_and_scoped(fresh_db, monkeypatch):
    _seed_db(fresh_db)
    
    class MockFitAgent:
        def evaluate(self, *args, **kwargs):
            return {"fit_status": "FIT", "fit_score": 90, "reason": "Good"}
            
    monkeypatch.setattr("osint_engine.product_qualification.ProductQualificationAgent", lambda db: MockFitAgent())

    client.post("/api/orchestrator/evaluate_fit", json={"product_id": 1})
    client.post("/api/orchestrator/evaluate_fit", json={"product_id": 1})
    
    conn = db_connector.get_connection(fresh_db)
    fits = conn.execute("SELECT prospect_id, product_id, fit_status FROM prospect_product_fit WHERE product_id = 1").fetchall()
    assert len(fits) == 1, "evaluate_fit must be idempotent"
    assert fits[0][0] == 1 # Prospect 1
    
    # Prospect 2 is REVIEW_REQUIRED (actually REJECTED from the seed db) and belongs to Prod 2. It shouldn't be touched by evaluate_fit(product_id=1) 
    
    jobs = conn.execute("SELECT count(*) FROM scheduled_jobs").fetchone()[0]
    emails = conn.execute("SELECT count(*) FROM email_archive").fetchone()[0]
    assert jobs == 0
    assert emails == 0

def test_evidence_review_gate_blocks_strategy_generation(fresh_db):
    _seed_db(fresh_db)
    conn = db_connector.get_connection(fresh_db)
    conn.execute("UPDATE prospects SET qualification_status='QUALIFIED' WHERE id=1")
    conn.execute("INSERT INTO prospect_product_fit (prospect_id, product_id, fit_status, reason) VALUES (1, 1, 'FIT', 'Good')")
    conn.commit()
    conn.close()

    ctx = {"product_id": 1, "research_campaign_id": 1, "market": "IT", "language": "EN", "target_segment": "SaaS", "buyer_role": "CEO"}
    
    # Attempt to generate strategy BEFORE reviewing evidence
    r = client.post("/api/sales_strategy/generate", json=ctx)
    assert r.status_code == 403
    assert "evidence" in r.json()["detail"].lower()

    # Human reviews and accepts evidence
    r = client.post("/api/orchestrator/prospect/1/review", json={"action": "APPROVE"})
    assert r.status_code == 200

    # Strategy generation now allowed
    r = client.post("/api/sales_strategy/generate", json=ctx)
    assert r.status_code != 403 # Will likely be 500 since AI isn't mocked here, but 403 is bypassed

def test_human_rejection_preserves_evidence(fresh_db):
    _seed_db(fresh_db)
    conn = db_connector.get_connection(fresh_db)
    conn.execute("UPDATE prospects SET qualification_status='QUALIFIED' WHERE id=1")
    conn.execute("INSERT INTO prospect_product_fit (prospect_id, product_id, fit_status, reason) VALUES (1, 1, 'FIT', 'Good')")
    conn.commit()
    conn.close()

    r = client.post("/api/orchestrator/prospect/1/review", json={"action": "REJECT", "reason": "Not quite right"})
    assert r.status_code == 200

    conn = db_connector.get_connection(fresh_db)
    qual = conn.execute("SELECT qualification_status, rejection_reason FROM prospects WHERE id=1").fetchone()
    assert qual[0] == "REJECTED"
    assert qual[1] == "Not quite right"
    
    fit = conn.execute("SELECT fit_status, reason FROM prospect_product_fit WHERE prospect_id=1 AND product_id=1").fetchone()
    assert fit[0] == "FIT"
    assert fit[1] == "Good" # AI evidence preserved

