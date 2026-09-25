import sqlite3
import os
import sys

def migrate(db_path="outreach_queue.sqlite3"):
    print(f"Running migration on {db_path}...")
    conn = sqlite3.connect(db_path)
    
    # 1. Add product_id to research_campaigns
    try:
        conn.execute("ALTER TABLE research_campaigns ADD COLUMN product_id INTEGER")
        print("Added 'product_id' to research_campaigns.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower() or "no such table" in str(e).lower():
            print(f"Skipped ALTER research_campaigns: {e}")
        else:
            raise

    # 2. Create prospect_product_fit table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prospect_product_fit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prospect_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            fit_status TEXT NOT NULL,
            fit_score INTEGER DEFAULT 0,
            reason TEXT,
            matched_signals TEXT,
            missing_signals TEXT,
            negative_signals TEXT,
            evidence_source_ids TEXT,
            provider TEXT,
            model TEXT,
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            UNIQUE(prospect_id, product_id)
        )
    """)
    print("Ensured 'prospect_product_fit' table exists.")

    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    db_file = "outreach_queue.sqlite3"
    if len(sys.argv) > 1:
        db_file = sys.argv[1]
    migrate(db_file)
