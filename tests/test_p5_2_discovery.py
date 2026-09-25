"""
tests/test_p5_2_discovery.py

Tests for P5.2B/P5.2C/P5.2D campaign builder and query generator.

Assertion history:
  P5.2E-R1 (2026-09-19): Updated fixture campaign_queries schema to match real DB
    (target_key, is_enabled columns added — previously missing, caused OperationalError).
  P5.2E-R1 (2026-09-19): Updated naming assertions to match P5.2C contract change:
    camp_name = "[Auto] Discovery: Product {id}" (was product_name).
    icp_name  = "[Auto] ICP: Product {id}" (was product_name).
  P5.2E-R1 (2026-09-19): Removed "Global" from assertions — P5.2D intentionally removed
    the "Global" default market fallback to avoid UNKNOWN leakage in queries.
    countries is now empty list [] when no geographic_markets specified.
"""
import os
import json
import sqlite3
import pytest
from product_intelligence.campaign_builder import create_campaign_from_product
from osint_engine.generator import QueryGenerator

@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test.db"

    from product_intelligence.store import ensure_schema
    ensure_schema(str(db_path))

    import migrate_v2
    migrate_v2.DB_PATH = str(db_path)
    migrate_v2.run_migration()

    import migration_p5_2e
    migration_p5_2e.migrate(str(db_path))

    conn = sqlite3.connect(db_path)

    # Initialize necessary tables using IF NOT EXISTS to avoid conflict with ensure_schema.
    conn.executescript("""
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
        CREATE TABLE IF NOT EXISTS sales_offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT NOT NULL,
            price TEXT,
            target_buyer_roles TEXT,
            created_at_utc TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS research_campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            offer_id INTEGER,
            icp_id INTEGER,
            status TEXT DEFAULT 'draft',
            created_at_utc TEXT NOT NULL,
            product_id INTEGER
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
            created_at_utc TEXT NOT NULL
        );
        -- P5.2E-R1: schema matches real production campaign_queries table.
        -- Previously missing: target_key, is_enabled (caused OperationalError).
        CREATE TABLE IF NOT EXISTS campaign_queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            family TEXT,
            query TEXT,
            target_key TEXT,
            is_enabled INTEGER DEFAULT 1,
            status TEXT,
            created_at_utc TEXT
        );
    """)

    profile_json = json.dumps({
        "product_name": "TestAI CRM",
        "description": "An AI-powered CRM.",
        "keywords": ["AI sales", "automated CRM"],
        "potential_buyer_roles": ["VP Sales", "CEO"],
        "pricing_information": {"status": "KNOWN", "summary": "$50/mo"}
        # NOTE: no geographic_markets — builder will produce empty countries (P5.2D contract)
    })

    conn.execute("INSERT INTO products (name, slug, status, created_at_utc, updated_at_utc, raw_summary) VALUES (?, ?, ?, 'now', 'now', ?)",
                 ("Test CRM", "test-crm", "READY", profile_json))

    conn.commit()
    conn.close()
    return str(db_path)


def test_campaign_creation_from_product(test_db):
    product_id = 1
    campaign_id = create_campaign_from_product(test_db, product_id)
    assert campaign_id is not None

    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row

    camp = conn.execute("SELECT * FROM research_campaigns WHERE id=?", (campaign_id,)).fetchone()
    assert camp is not None
    # P5.2E-R1: P5.2C changed naming from product_name to product_id-based.
    # OLD: assert "TestAI CRM" in camp["name"]
    # NEW: builder uses "[Auto] Discovery: Product {id}"
    assert "Discovery: Product 1" in camp["name"]

    icp = conn.execute("SELECT * FROM ideal_customer_profiles WHERE id=?", (camp["icp_id"],)).fetchone()
    assert icp is not None
    # P5.2E-R1: P5.2C changed naming from product_name to product_id-based.
    # OLD: assert "TestAI CRM" in icp["name"]
    # NEW: builder uses "[Auto] ICP: Product {id}"
    assert "ICP: Product 1" in icp["name"]
    assert "VP Sales" in icp["roles"]
    # P5.2E-R1: P5.2D removed "Global" fallback. No markets in profile → empty list.
    # OLD: assert "Global" in icp["countries"]
    # NEW: empty list when no geographic_markets provided
    assert icp["countries"] == "[]"

    offer = conn.execute("SELECT * FROM sales_offers WHERE id=?", (camp["offer_id"],)).fetchone()
    assert offer is not None
    assert "$50/mo" in offer["price"]
    assert "An AI-powered CRM" in offer["description"]

    # 2 keywords, no markets, no company_types, no industries:
    # Per keyword: 1 PERSON_DISCOVERY + 2 COMPANY_DISCOVERY = 3 templates
    # Total: 2 keywords * 3 = 6 templates — UNCHANGED from original assertion
    templates = conn.execute("SELECT * FROM query_templates WHERE campaign_id=?", (campaign_id,)).fetchall()
    assert len(templates) == 6

    conn.close()


def test_concrete_query_expansion(test_db):
    product_id = 1
    campaign_id = create_campaign_from_product(test_db, product_id)

    gen = QueryGenerator(test_db)
    queries = gen.get_concrete_queries(campaign_id)

    assert len(queries) > 0
    query_strings = [q["query"] for q in queries]

    # P5.2E-R1: P5.2D removed "Global" suffix from queries when no geographic_markets.
    # OLD assertions (all failed due to "Global" suffix):
    #   assert '"AI sales" "VP Sales" Global' in query_strings
    #   assert '"AI sales" "CEO" Global' in query_strings
    #   assert '"automated CRM" "VP Sales" Global' in query_strings
    #   assert '"AI sales" companies Global' in query_strings
    #   assert 'B2B "automated CRM" Global' in query_strings
    # NEW assertions (no Global suffix, same query structure verified):
    assert '"AI sales" "VP Sales"' in query_strings
    assert '"AI sales" "CEO"' in query_strings
    assert '"automated CRM" "VP Sales"' in query_strings
    assert '"AI sales" companies' in query_strings
    assert 'B2B "automated CRM"' in query_strings
