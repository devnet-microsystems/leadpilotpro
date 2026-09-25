"""
schema_bootstrap.py

Crea (o completa) lo schema COMPLETO di LeadPilot Pro in modo idempotente.

Perché esiste: fino a P5.3 lo schema veniva costruito da script separati lanciati a mano
(migrate_v2.py, migration_p5_*.py, ...). Su un database nuovo mancavano 13 tabelle
(templates, research_campaigns, ideal_customer_profiles, sales_offers, ...) e metà
dell'interfaccia rispondeva 500. Questo modulo viene chiamato all'avvio del server e dai test.

Le definizioni delle tabelle aggiunte qui sono quelle del database di produzione.
Non modifica mai dati esistenti: solo CREATE ... IF NOT EXISTS e ADD COLUMN mancanti.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

EXTRA_DDL = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY, prospect_id INTEGER, timestamp_utc TEXT, action TEXT, details TEXT
);

CREATE TABLE IF NOT EXISTS templates (
    name TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    created_at_utc TEXT NOT NULL
);

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
    product_id INTEGER REFERENCES products(id),
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
    created_at TIMESTAMP,
    campaign_id INTEGER,
    template_id INTEGER
);

CREATE TABLE IF NOT EXISTS campaign_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER, family TEXT, query TEXT, target_key TEXT,
    is_enabled INTEGER DEFAULT 1, status TEXT DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS prospect_sources (
    id INTEGER PRIMARY KEY,
    prospect_id INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    engine TEXT,
    source_url TEXT,
    query TEXT,
    discovered_at TEXT NOT NULL,
    query_run_id TEXT DEFAULT '',
    FOREIGN KEY (prospect_id) REFERENCES prospects(id)
);

CREATE TABLE IF NOT EXISTS prospect_product_fit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
    fit_status TEXT NOT NULL, fit_score INTEGER, reason TEXT,
    matched_signals TEXT, missing_signals TEXT, negative_signals TEXT,
    evidence_source_ids TEXT, provider TEXT, model TEXT, analysis_version TEXT,
    created_at_utc TEXT, updated_at_utc TEXT, evidence_reviewed_at TEXT,
    UNIQUE(prospect_id, product_id)
);

CREATE TABLE IF NOT EXISTS outbound_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    prospect_id INTEGER NOT NULL,
    sequence_step INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    scheduled_at_utc TEXT NOT NULL,
    provider_request_id TEXT,
    provider_status TEXT,
    last_error TEXT,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    UNIQUE(campaign_id, prospect_id, sequence_step)
);
"""

# colonne che gli script di migrazione storici aggiungevano a mano
_PROSPECT_COLUMNS = {
    "contact_score": "REAL",
    "research_campaign_id": "INTEGER",
    "why_matched": "TEXT DEFAULT ''",
}


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    for name, decl in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


def ensure_all_schema(db_path) -> None:
    """Crea/completa lo schema. Sicuro da chiamare a ogni avvio e su DB già popolati."""
    from outreach_sender import OutreachDatabase  # crea le tabelle base e l'utente admin al primo avvio
    import product_intelligence.store as pi_store
    import migration_p5_3a

    db_path = Path(db_path)
    base = OutreachDatabase(db_path)
    base.connection.close()

    pi_store.ensure_schema(str(db_path))  # products, product_sources

    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(EXTRA_DDL)
        _ensure_columns(conn, "prospects", _PROSPECT_COLUMNS)
        _ensure_columns(conn, "prospect_product_fit", {"evidence_reviewed_at": "TEXT"})
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('market_mode', 'international')")
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('language', 'en')")
        conn.commit()
    finally:
        conn.close()

    migration_p5_3a.migrate(str(db_path))  # product_sales_strategies, product_campaigns, email_sequence_messages
