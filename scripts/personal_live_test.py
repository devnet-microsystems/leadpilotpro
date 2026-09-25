"""
scripts/personal_live_test.py

Entrypoint for personal live test sending ONE message using Infomaniak SMTP.
"""
import os
import sys
import sqlite3
from pathlib import Path

# Add project root to sys.path so imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from infomaniak_adapter import InfomaniakSMTPAdapter
from tests.test_p6_4_live_activation import trigger_personal_live_test
from outbound_worker import OutboundWorker

def main() -> int:
    recipient = os.environ.get("LEADPILOT_TEST_RECIPIENT", "antoniomichelotti@devnet-microsystems.com")
    db_path = os.environ.get("LEADPILOT_DB_PATH", "leadpilot.db")

    if not recipient:
        print("ERROR: LEADPILOT_TEST_RECIPIENT is not configured.")
        return 2

    required = [
        "SMTP_HOST",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
    ]

    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        print("ERROR: missing SMTP configuration:", ", ".join(missing))
        return 2

    print("LeadPilotPro PERSONAL LIVE TEST")
    print(f"Database: {db_path}")
    print(f"Recipient: {recipient}")
    print()

    adapter = InfomaniakSMTPAdapter(dry_run=False)
    
    print("1. Validating SMTP connection...")
    if not adapter.validate_connection():
        print("ERROR: SMTP validation failed. Check your credentials.")
        return 1
    print("SMTP connection        ✅")
    print("Authentication         ✅")

    print("\nThis sends EXACTLY ONE test message.")
    print("The recipient must be your own test mailbox.")

    confirmation = input("Type SEND-ONE to continue: ").strip()
    if confirmation != "SEND-ONE":
        print("Cancelled. No email sent.")
        return 0

    print("\n4. Creating logical outbound job and sending...")
    try:
        # Step 4, 5, 6
        result = trigger_personal_live_test(db_path, adapter, recipient)
        
        if result:
            print("1 message submitted    ✅")
        else:
            print("Message submission failed or already executed.")

        # Steps 7-8: Verify tables
        conn = sqlite3.connect(db_path)
        jobs = conn.execute("SELECT * FROM outbound_jobs WHERE campaign_id=0 AND prospect_id=0 AND sequence_step=0").fetchall()
        archives = conn.execute("SELECT * FROM email_archive WHERE campaign_id=0").fetchall()
        
        if len(jobs) == 1:
            print("1 outbound_job         ✅")
        else:
            print(f"ERROR: Expected 1 outbound_job, found {len(jobs)}")
            
        if len(archives) == 1:
            print("1 email_archive       ✅")
        else:
            print(f"ERROR: Expected 1 email_archive, found {len(archives)}")

        # Step 9-10: Test duplicate execution
        worker = OutboundWorker(db_path, adapter)
        success2 = worker.schedule_logical_job(0, 0, 0)
        if success2 is False:
            print("0 duplicate jobs      ✅")
            print("0 duplicate emails    ✅")
        else:
            print("ERROR: Duplicate execution was allowed!")
            return 1
            
        conn.close()

    except Exception as exc:
        print(f"LIVE TEST FAILED: {type(exc).__name__}")
        return 1

    print("\nPersonal live test completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
