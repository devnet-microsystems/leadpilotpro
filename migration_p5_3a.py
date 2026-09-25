"""
migration_p5_3a.py

Migration script for P5.3A: Product -> Sales Strategy -> Email Campaign.
Creates tables for product-driven email sequences, completely separate from the legacy
campaigns/templates system.

Idempotent: safe to run multiple times.
"""
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def migrate(db_path: str):
    logger.info(f"Running P5.3A migration on {db_path}...")
    conn = sqlite3.connect(db_path)
    
    # 1. product_sales_strategies
    conn.execute("""
        CREATE TABLE IF NOT EXISTS product_sales_strategies (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id              INTEGER NOT NULL,
            research_campaign_id    INTEGER,
            market                  TEXT NOT NULL DEFAULT '',
            language                TEXT NOT NULL DEFAULT 'English',
            target_segment          TEXT NOT NULL DEFAULT '',
            buyer_role              TEXT NOT NULL DEFAULT '',
            core_value_proposition  TEXT,
            pain_points             TEXT,
            proof_points            TEXT,
            primary_cta             TEXT,
            tone                    TEXT NOT NULL DEFAULT 'professional',
            sequence_strategy       TEXT,
            personalization_fields  TEXT,
            provider                TEXT,
            model                   TEXT,
            created_at_utc          TEXT NOT NULL,
            updated_at_utc          TEXT NOT NULL,
            UNIQUE(product_id, research_campaign_id, market, language, target_segment, buyer_role)
        )
    """)
    
    # 2. product_campaigns
    conn.execute("""
        CREATE TABLE IF NOT EXISTS product_campaigns (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            name                    TEXT NOT NULL,
            product_id              INTEGER NOT NULL,
            research_campaign_id    INTEGER,
            strategy_id             INTEGER,
            market                  TEXT NOT NULL DEFAULT '',
            language                TEXT NOT NULL DEFAULT 'English',
            target_segment          TEXT NOT NULL DEFAULT '',
            buyer_role              TEXT NOT NULL DEFAULT '',
            sequence_length         INTEGER NOT NULL DEFAULT 4,
            status                  TEXT NOT NULL DEFAULT 'DRAFT',
            created_at_utc          TEXT NOT NULL,
            updated_at_utc          TEXT NOT NULL,
            UNIQUE(product_id, research_campaign_id, market, language, target_segment, buyer_role)
        )
    """)
    
    # 3. email_sequence_messages
    conn.execute("""
        CREATE TABLE IF NOT EXISTS email_sequence_messages (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            product_campaign_id     INTEGER NOT NULL,
            sequence_order          INTEGER NOT NULL,
            purpose                 TEXT NOT NULL,
            language                TEXT NOT NULL DEFAULT 'English',
            subject                 TEXT NOT NULL,
            body                    TEXT NOT NULL,
            cta                     TEXT,
            delay_days              INTEGER NOT NULL DEFAULT 0,
            personalization_fields  TEXT,
            status                  TEXT DEFAULT 'DRAFT',
            created_at_utc          TEXT NOT NULL,
            UNIQUE(product_campaign_id, sequence_order),
            FOREIGN KEY(product_campaign_id) REFERENCES product_campaigns(id)
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info("P5.3A migration completed successfully.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    db_file = "outreach_queue.sqlite3"
    if Path(db_file).exists():
        migrate(db_file)
    else:
        logger.warning(f"Database {db_file} not found.")
