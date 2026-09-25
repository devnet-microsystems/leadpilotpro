"""
outbound_worker.py

Execution engine for P6. 
Enforces EXPORT != SEND, idempotency, and error handling.
"""
import sqlite3
import db_connector
import time
from typing import Optional, List, Dict, Any
from provider_adapter import EmailProvider, TransportState

class OutboundWorker:
    def __init__(self, db_path: str, provider: EmailProvider):
        self.db_path = db_path
        self.provider = provider
        self.paused = False

    def get_connection(self) -> sqlite3.Connection:
        conn = db_connector.get_connection(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def schedule_logical_job(self, campaign_id: int, prospect_id: int, sequence_step: int) -> bool:
        """
        Creates a logical job in outbound_jobs.
        Returns True if scheduled, False if already exists.
        """
        conn = self.get_connection()
        try:
            now_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            conn.execute("""
                INSERT INTO outbound_jobs (campaign_id, prospect_id, sequence_step, status, scheduled_at_utc, created_at_utc, updated_at_utc)
                VALUES (?, ?, ?, 'pending', ?, ?, ?)
            """, (campaign_id, prospect_id, sequence_step, now_iso, now_iso, now_iso))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def claim_next_job(self, conn: sqlite3.Connection) -> Optional[sqlite3.Row]:
        """
        Atomically claims a pending job.
        """
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        now_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        row = cursor.execute("""
            SELECT * FROM outbound_jobs 
            WHERE status = 'pending' AND scheduled_at_utc <= ?
            ORDER BY id ASC LIMIT 1
        """, (now_iso,)).fetchone()
        
        if row:
            now_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            cursor.execute("UPDATE outbound_jobs SET status = 'claimed', updated_at_utc = ? WHERE id = ?", (now_iso, row["id"]))
        conn.commit()
        return row

    def execute_job(self, job_id: int):
        if self.paused:
            return

        conn = self.get_connection()
        try:
            # Re-fetch the job to ensure it's still claimed and valid
            job = conn.execute("SELECT * FROM outbound_jobs WHERE id = ?", (job_id,)).fetchone()
            if not job or job["status"] != "claimed":
                return

            prospect = conn.execute("SELECT business_email FROM prospects WHERE id = ?", (job["prospect_id"],)).fetchone()
            if not prospect:
                conn.execute("UPDATE outbound_jobs SET status = 'failed', last_error = 'Prospect not found' WHERE id = ?", (job_id,))
                conn.commit()
                return

            email = prospect["business_email"]
            subject = f"Campaign {job['campaign_id']} step {job['sequence_step']}"
            body = "Test body"
            
            idempotency_metadata = {
                "campaign_id": str(job["campaign_id"]),
                "prospect_id": str(job["prospect_id"]),
                "sequence_step": str(job["sequence_step"])
            }

            result = self.provider.send_email(email, subject, body, idempotency_metadata)
            
            now_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            
            if result.state == TransportState.PROVIDER_ACCEPTED:
                # Success
                conn.execute("UPDATE outbound_jobs SET status = 'completed', provider_request_id = ?, updated_at_utc = ? WHERE id = ?", 
                            (result.provider_request_id, now_iso, job_id))
                conn.execute("INSERT INTO email_archive (business_email, campaign_id, sent_at_utc, message_text) VALUES (?, ?, ?, ?)",
                            (email, job["campaign_id"], now_iso, body))
                
            elif result.state == TransportState.REQUEST_NOT_SENT:
                # Network error, safe to retry. We revert to pending and delay.
                next_run_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() + 60))
                conn.execute("UPDATE outbound_jobs SET status = 'pending', scheduled_at_utc = ?, last_error = ?, updated_at_utc = ? WHERE id = ?", 
                            (next_run_iso, result.last_error, now_iso, job_id))
                            
            elif result.state == TransportState.REQUEST_SENT_OUTCOME_UNKNOWN:
                # AMBIGUOUS
                conn.execute("UPDATE outbound_jobs SET status = 'ambiguous', last_error = ?, updated_at_utc = ? WHERE id = ?", 
                            (result.last_error, now_iso, job_id))
                            
            elif result.state == TransportState.PROVIDER_REJECTED:
                if "429" in (result.last_error or ""):
                    # Rate limit. Revert to pending, delay.
                    next_run_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() + 60))
                    conn.execute("UPDATE outbound_jobs SET status = 'pending', scheduled_at_utc = ?, last_error = ?, updated_at_utc = ? WHERE id = ?", 
                                (next_run_iso, result.last_error, now_iso, job_id))
                elif "401" in (result.last_error or "") or "403" in (result.last_error or "") or "SMTP_AUTH_FAILURE" in (result.last_error or ""):
                    # Auth failure. Non-retryable execution error. Pause worker.
                    self.paused = True
                    conn.execute("UPDATE outbound_jobs SET status = 'failed', last_error = ?, updated_at_utc = ? WHERE id = ?", 
                                (result.last_error, now_iso, job_id))
                elif "400" in (result.last_error or ""):
                    # Malformed request. Non-retryable execution error.
                    conn.execute("UPDATE outbound_jobs SET status = 'failed', last_error = ?, updated_at_utc = ? WHERE id = ?", 
                                (result.last_error, now_iso, job_id))
                elif "Recipient Rejected" in (result.last_error or ""):
                    # Hard bounce equivalent
                    conn.execute("UPDATE outbound_jobs SET status = 'failed', last_error = ?, updated_at_utc = ? WHERE id = ?", 
                                (result.last_error, now_iso, job_id))
                    conn.execute("UPDATE prospects SET qualification_status = 'REJECTED' WHERE id = ?", (job["prospect_id"],))
                else:
                    # Generic rejection
                    conn.execute("UPDATE outbound_jobs SET status = 'failed', last_error = ?, updated_at_utc = ? WHERE id = ?", 
                                (result.last_error, now_iso, job_id))

            conn.commit()

        finally:
            conn.close()

    def process_queue(self):
        conn = self.get_connection()
        try:
            while not self.paused:
                job = self.claim_next_job(conn)
                if not job:
                    break
                self.execute_job(job["id"])
        finally:
            conn.close()
