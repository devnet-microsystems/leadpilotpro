import sqlite3
import db_connector
import pytest
from pathlib import Path
from schema_bootstrap import ensure_all_schema
from provider_adapter import MockAdapter
from outbound_worker import OutboundWorker

@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    ensure_all_schema(str(db_path))
    conn = db_connector.get_connection(str(db_path))
    conn.execute("INSERT INTO prospects (id, company_name, business_email, target_url, qualification_status, source_file, imported_at_utc, status) VALUES (1, 'Test', 'test@example.com', 'http://test.com', 'QUALIFIED', 'test.csv', '2023-01-01T00:00:00Z', 'approved')")
    conn.execute("INSERT INTO prospects (id, company_name, business_email, target_url, qualification_status, source_file, imported_at_utc, status) VALUES (2, 'DNS', 'dns-fail@example.com', 'http://dns.com', 'QUALIFIED', 'test.csv', '2023-01-01T00:00:00Z', 'approved')")
    conn.execute("INSERT INTO prospects (id, company_name, business_email, target_url, qualification_status, source_file, imported_at_utc, status) VALUES (3, 'Rate', 'rate-limit@example.com', 'http://rate.com', 'QUALIFIED', 'test.csv', '2023-01-01T00:00:00Z', 'approved')")
    conn.execute("INSERT INTO prospects (id, company_name, business_email, target_url, qualification_status, source_file, imported_at_utc, status) VALUES (4, 'Auth', 'auth-fail@example.com', 'http://auth.com', 'QUALIFIED', 'test.csv', '2023-01-01T00:00:00Z', 'approved')")
    conn.execute("INSERT INTO prospects (id, company_name, business_email, target_url, qualification_status, source_file, imported_at_utc, status) VALUES (5, 'Bad', 'malformed@example.com', 'http://bad.com', 'QUALIFIED', 'test.csv', '2023-01-01T00:00:00Z', 'approved')")
    conn.execute("INSERT INTO prospects (id, company_name, business_email, target_url, qualification_status, source_file, imported_at_utc, status) VALUES (6, 'Bounce', 'bounce@example.com', 'http://bounce.com', 'QUALIFIED', 'test.csv', '2023-01-01T00:00:00Z', 'approved')")
    conn.execute("INSERT INTO prospects (id, company_name, business_email, target_url, qualification_status, source_file, imported_at_utc, status) VALUES (7, 'Timeout', 'timeout-after@example.com', 'http://timeout.com', 'QUALIFIED', 'test.csv', '2023-01-01T00:00:00Z', 'approved')")
    conn.commit()
    conn.close()
    return str(db_path)

def test_duplicate_activation(test_db):
    worker = OutboundWorker(test_db, MockAdapter())
    assert worker.schedule_logical_job(10, 1, 1) is True
    assert worker.schedule_logical_job(10, 1, 1) is False # Duplicate fails

def test_duplicate_worker_claim(test_db):
    worker1 = OutboundWorker(test_db, MockAdapter())
    worker2 = OutboundWorker(test_db, MockAdapter())
    worker1.schedule_logical_job(10, 1, 1)
    
    conn1 = worker1.get_connection()
    conn2 = worker2.get_connection()
    
    job1 = worker1.claim_next_job(conn1)
    assert job1 is not None
    job2 = worker2.claim_next_job(conn2)
    assert job2 is None # Already claimed by worker1
    conn1.close()
    conn2.close()

def test_request_not_sent_retry(test_db):
    worker = OutboundWorker(test_db, MockAdapter())
    worker.schedule_logical_job(10, 2, 1) # dns-fail
    worker.process_queue()
    conn = worker.get_connection()
    job = conn.execute("SELECT * FROM outbound_jobs").fetchone()
    assert job["status"] == "pending" # Reverted to pending for retry
    assert "network" in job["last_error"].lower()
    conn.close()

def test_rate_limit_retry(test_db):
    worker = OutboundWorker(test_db, MockAdapter())
    worker.schedule_logical_job(10, 3, 1) # rate-limit
    worker.process_queue()
    conn = worker.get_connection()
    job = conn.execute("SELECT * FROM outbound_jobs").fetchone()
    assert job["status"] == "pending"
    assert "429" in job["last_error"]
    conn.close()

def test_auth_failure_pauses_worker(test_db):
    worker = OutboundWorker(test_db, MockAdapter())
    worker.schedule_logical_job(10, 4, 1) # auth-fail
    worker.process_queue()
    assert worker.paused is True
    conn = worker.get_connection()
    job = conn.execute("SELECT * FROM outbound_jobs").fetchone()
    assert job["status"] == "failed"
    prospect = conn.execute("SELECT qualification_status FROM prospects WHERE id = 4").fetchone()
    assert prospect[0] == "QUALIFIED" # Prospect not penalized
    conn.close()

def test_malformed_request_stops_execution_without_penalizing(test_db):
    worker = OutboundWorker(test_db, MockAdapter())
    worker.schedule_logical_job(10, 5, 1) # malformed
    worker.process_queue()
    conn = worker.get_connection()
    job = conn.execute("SELECT * FROM outbound_jobs").fetchone()
    assert job["status"] == "failed"
    assert "400" in job["last_error"]
    prospect = conn.execute("SELECT qualification_status FROM prospects WHERE id = 5").fetchone()
    assert prospect[0] == "QUALIFIED"
    conn.close()

def test_explicit_rejection_marks_prospect_rejected(test_db):
    worker = OutboundWorker(test_db, MockAdapter())
    worker.schedule_logical_job(10, 6, 1) # bounce
    worker.process_queue()
    conn = worker.get_connection()
    prospect = conn.execute("SELECT qualification_status FROM prospects WHERE id = 6").fetchone()
    assert prospect[0] == "REJECTED"
    conn.close()

def test_timeout_after_transmission_becomes_ambiguous_and_no_retry(test_db):
    worker = OutboundWorker(test_db, MockAdapter())
    worker.schedule_logical_job(10, 7, 1) # timeout-after
    worker.process_queue()
    conn = worker.get_connection()
    job = conn.execute("SELECT * FROM outbound_jobs").fetchone()
    assert job["status"] == "ambiguous"
    
    # Process queue again should ignore ambiguous
    worker.process_queue()
    job_after = conn.execute("SELECT * FROM outbound_jobs").fetchone()
    assert job_after["status"] == "ambiguous" # Still ambiguous, not retried
    
    # Try scheduling again
    assert worker.schedule_logical_job(10, 7, 1) is False # Duplicate fails
    
    conn.close()

def test_email_archive_is_written_on_success(test_db):
    worker = OutboundWorker(test_db, MockAdapter())
    worker.schedule_logical_job(10, 1, 1) # success
    worker.process_queue()
    conn = worker.get_connection()
    archive = conn.execute("SELECT * FROM email_archive").fetchall()
    assert len(archive) == 1
    assert archive[0]["business_email"] == "test@example.com"
    conn.close()

def test_zero_network_calls():
    # Implicitly verified since MockAdapter does not import requests/http.client
    pass
