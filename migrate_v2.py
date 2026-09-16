import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("outreach_queue.sqlite3")

def run_migration():
    print(f"Migrating {DB_PATH} to LeadPilot 2.0 Schema...")
    conn = sqlite3.connect(DB_PATH)
    
    # 1. New Tables
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sales_offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT NOT NULL,
            price TEXT,
            target_buyer_roles TEXT,
            created_at_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ideal_customer_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            roles TEXT NOT NULL,
            industries TEXT NOT NULL,
            company_sizes TEXT NOT NULL,
            countries TEXT NOT NULL,
            languages TEXT NOT NULL,
            created_at_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS research_campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            offer_id INTEGER,
            icp_id INTEGER,
            status TEXT DEFAULT 'draft',
            created_at_utc TEXT NOT NULL,
            FOREIGN KEY(offer_id) REFERENCES sales_offers(id),
            FOREIGN KEY(icp_id) REFERENCES ideal_customer_profiles(id)
        );

        CREATE TABLE IF NOT EXISTS query_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            family TEXT NOT NULL,
            template TEXT NOT NULL,
            variables TEXT,
            enabled INTEGER DEFAULT 1,
            priority INTEGER DEFAULT 0,
            base_score REAL DEFAULT 50.0,
            created_at_utc TEXT NOT NULL,
            FOREIGN KEY(campaign_id) REFERENCES research_campaigns(id)
        );
        
        -- Make sure query_runs exists before altering
        CREATE TABLE IF NOT EXISTS query_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            target_key TEXT,
            query_template TEXT,
            query TEXT NOT NULL,
            family TEXT NOT NULL,
            round INTEGER,
            provider TEXT NOT NULL,
            raw_results INTEGER,
            unique_domains INTEGER,
            new_domains INTEGER,
            emails_found INTEGER,
            duration_ms INTEGER,
            status TEXT DEFAULT 'SUCCESS',
            provider_state TEXT DEFAULT '',
            created_at TIMESTAMP
        );
    """)

    # 2. Alter existing tables (ignore errors if columns already exist)
    alters = [
        "ALTER TABLE query_runs ADD COLUMN campaign_id INTEGER;",
        "ALTER TABLE query_runs ADD COLUMN template_id INTEGER;",
        "ALTER TABLE prospects ADD COLUMN research_campaign_id INTEGER;",
        "ALTER TABLE prospects ADD COLUMN why_matched TEXT DEFAULT '';"
    ]
    
    for stmt in alters:
        try:
            conn.execute(stmt)
            print(f"Applied: {stmt}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"Skipped (already exists): {stmt}")
            else:
                print(f"Error on '{stmt}': {e}")
                
    # 3. Default Settings
    try:
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('market_mode', 'international')")
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('language', 'en')")
    except Exception as e:
        print(f"Settings error: {e}")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    run_migration()
