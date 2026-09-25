import pytest
import sqlite3
import db_connector
from unittest.mock import patch

from infomaniak_adapter import InfomaniakSMTPAdapter
from outbound_worker import OutboundWorker
from schema_bootstrap import ensure_all_schema

def trigger_personal_live_test(db_path: str, adapter: InfomaniakSMTPAdapter, test_recipient: str):
    """
    Triggers exactly ONE test message to the specified recipient.
    This bypasses normal campaign activation but enforces the outbound execution engine safety constraints.
    """
    worker = OutboundWorker(db_path, adapter)
    
    # We use a special logical identity for the test message: campaign 0, prospect 0, step 0
    success = worker.schedule_logical_job(0, 0, 0)
    
    if not success:
        print("Test job already scheduled/executed.")
        return False
        
    conn = worker.get_connection()
    try:
        job = worker.claim_next_job(conn)
        if job:
            # Re-fetch the job to ensure it's still claimed and valid
            job = conn.execute("SELECT * FROM outbound_jobs WHERE id = ?", (job["id"],)).fetchone()
            if job and job["status"] == "claimed":
                # Execute the send_test_message which uses the safe single-message method
                result = adapter.send_test_message(test_recipient)
                
                import time
                now_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                
                # Verify exactly one appropriate email_archive record
                if result.state == "PROVIDER_ACCEPTED":
                    conn.execute("UPDATE outbound_jobs SET status = 'completed', provider_request_id = ?, updated_at_utc = ? WHERE id = ?", 
                                (result.provider_request_id, now_iso, job["id"]))
                    conn.execute("INSERT INTO email_archive (business_email, campaign_id, sent_at_utc, message_text) VALUES (?, ?, ?, ?)",
                                (test_recipient, 0, now_iso, "Test Message"))
                conn.commit()
    finally:
        conn.close()
    return True

@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    ensure_all_schema(str(db_path))
    return str(db_path)

@patch("infomaniak_adapter.smtplib.SMTP")
def test_personal_live_activation_exactly_one_message(mock_smtp, test_db):
    mock_instance = mock_smtp.return_value.__enter__.return_value
    adapter = InfomaniakSMTPAdapter(dry_run=False)
    
    test_email = "operator@example.com"
    
    # 1. Trigger the test
    success = trigger_personal_live_test(test_db, adapter, test_email)
    assert success is True
    
    # 2. Verify exactly one message was transmitted
    assert mock_instance.send_message.call_count == 1
    
    # 3. Verify exactly one outbound job
    conn = db_connector.get_connection(test_db)
    jobs = conn.execute("SELECT * FROM outbound_jobs WHERE campaign_id=0").fetchall()
    assert len(jobs) == 1
    assert jobs[0][4] == "completed" # status
    
    # 4. Verify exactly one email_archive record
    archives = conn.execute("SELECT * FROM email_archive").fetchall()
    assert len(archives) == 1
    assert archives[0][1] == test_email
    
    # 5. Try again, ensure it does NOT send a second message due to idempotency
    success2 = trigger_personal_live_test(test_db, adapter, test_email)
    assert success2 is False
    assert mock_instance.send_message.call_count == 1 # Still 1
    
    jobs2 = conn.execute("SELECT * FROM outbound_jobs WHERE campaign_id=0").fetchall()
    assert len(jobs2) == 1 # Still 1 job
    
    archives2 = conn.execute("SELECT * FROM email_archive").fetchall()
    assert len(archives2) == 1 # Still 1 archive
    
    conn.close()
