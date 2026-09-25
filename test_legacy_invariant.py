import sqlite3
import sys

def check_legacy_invariant():
    conn = sqlite3.connect('/Users/tonic/Lavori/LeadPilotPro/leadpilot.db')
    try:
        send_jobs = conn.execute("SELECT COUNT(*) FROM send_jobs").fetchone()[0]
    except:
        send_jobs = 0
    try:
        archive = conn.execute("SELECT COUNT(*) FROM email_archive").fetchone()[0]
    except:
        archive = 0
        
    print(f"Legacy Invariant Check:")
    print(f"send_jobs count: {send_jobs}")
    print(f"email_archive count: {archive}")
    
    if send_jobs == 0 and archive == 0:
        print("PASS: No legacy tables were mutated.")
        sys.exit(0)
    else:
        print("FAIL: Legacy tables were mutated!")
        sys.exit(1)

if __name__ == "__main__":
    check_legacy_invariant()
