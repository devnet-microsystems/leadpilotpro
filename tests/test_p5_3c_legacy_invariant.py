import sqlite3
import db_connector
import pytest
from fastapi.testclient import TestClient
from web_server import app

client = TestClient(app)

def test_legacy_invariant_delta(tmp_path):
    db_path = str(tmp_path / "test_legacy.sqlite3")
    from schema_bootstrap import ensure_all_schema
    ensure_all_schema(db_path)
    
    conn = db_connector.get_connection(db_path)
    
    # Pre-populate some legacy data to prove we measure delta
    conn.execute("INSERT INTO scheduled_jobs (id, campaign_id, daily_limit, scheduled_at_utc) VALUES (1, 999, 100, 'now')")
    conn.execute("INSERT INTO email_archive (id, business_email, sent_at_utc, message_text) VALUES (1, 'e@e.com', 'now', 'msg')")
    
    # Also create the necessary data to run evaluate_fit
    conn.execute("INSERT INTO products (id, name, slug, status, raw_summary, created_at_utc, updated_at_utc) VALUES (1, 'Prod', 'prod', 'READY', '{}', 'now', 'now')")
    conn.execute("INSERT INTO prospects (id, company_name, business_email, target_url, source_file, imported_at_utc, status, qualification_status) VALUES (1, 'C', 'c@c.com', 'x', 'x', 'now', 'pending_review', 'REVIEW_REQUIRED')")
    conn.commit()
    
    before_scheduled_jobs = conn.execute("SELECT COUNT(*) FROM scheduled_jobs").fetchone()[0]
    before_archive = conn.execute("SELECT COUNT(*) FROM email_archive").fetchone()[0]
    
    assert before_scheduled_jobs == 1
    assert before_archive == 1
    
    # Overwrite DB_PATH to use our test DB for API calls
    import web_server
    old_db = web_server.DB_PATH
    web_server.DB_PATH = db_path
    
    # Run Orchestrator flow
    try:
        # evaluate fit
        client.post("/api/orchestrator/evaluate_fit", json={"product_id": 1})
        # review
        client.post("/api/orchestrator/prospect/1/review", json={"action": "REJECT", "reason": "Test"})
    finally:
        web_server.DB_PATH = old_db
        
    after_scheduled_jobs = conn.execute("SELECT COUNT(*) FROM scheduled_jobs").fetchone()[0]
    after_archive = conn.execute("SELECT COUNT(*) FROM email_archive").fetchone()[0]
    
    assert after_scheduled_jobs == before_scheduled_jobs, f"scheduled_jobs changed from {before_scheduled_jobs} to {after_scheduled_jobs}"
    assert after_archive == before_archive, f"email_archive changed from {before_archive} to {after_archive}"
    conn.close()

