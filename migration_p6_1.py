"""
migration_p6_1.py

Creates the outbound_jobs table which enforces the idempotency constraint
campaign_id + prospect_id + sequence_step
as required by the P6.1 Integration Contract.
"""

import sqlite3
import db_connector
from pathlib import Path

def migrate(db_path: str):
    conn = db_connector.get_connection(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS outbound_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                prospect_id INTEGER NOT NULL,
                sequence_step INTEGER NOT NULL,
                status TEXT DEFAULT 'pending', -- pending, claimed, ambiguous, completed, failed
                scheduled_at_utc TEXT NOT NULL,
                provider_request_id TEXT,
                provider_status TEXT,
                last_error TEXT,
                created_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL,
                UNIQUE(campaign_id, prospect_id, sequence_step)
            )
        """)
        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    db_file = Path(__file__).parent / "outreach_queue.sqlite3"
    if db_file.exists():
        migrate(str(db_file))
        print("P6.1 migration applied successfully.")
    else:
        print(f"Database {db_file} not found. Skipping migration.")
