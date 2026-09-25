import sqlite3
import db_connector
import pytest
import os
import json
from pathlib import Path

from public_osint_market_research import LeadStore
from osint_engine.models import DiscoveredLead
from outreach_sender import OutreachDatabase
from migrate_v2 import run_migration

# Fixture to set up DB schema
@pytest.fixture
def db_path(tmp_path):
    db_file = tmp_path / "test_p5_2e.sqlite3"
    
    # Init basic tables (simulating LeadPilot 1.0)
    conn = db_connector.get_connection(str(db_file))
    # the LeadStore will init some
    conn.close()
    
    # Use outreach sender to init campaigns, prospects etc
    db = OutreachDatabase(db_file)
    db.close()
    
    # Run migration v2
    import migrate_v2
    migrate_v2.DB_PATH = str(db_file)
    migrate_v2.run_migration()
    
    # Run p5_2e migration
    import migration_p5_2e
    migration_p5_2e.migrate(str(db_file))
    
    import product_intelligence.store
    product_intelligence.store.ensure_schema(str(db_file))
    
    return str(db_file)


def insert_product(db_path, name, summary="{}"):
    conn = db_connector.get_connection(db_path)
    cur = conn.execute("INSERT INTO products (name, slug, status, raw_summary, created_at_utc, updated_at_utc) VALUES (?, ?, 'READY', ?, '2026-09-19', '2026-09-19')", (name, name.lower().replace(" ", "-"), summary))
    conn.commit()
    return cur.lastrowid

def insert_research_campaign(db_path, name, product_id=None):
    conn = db_connector.get_connection(db_path)
    cur = conn.execute("INSERT INTO research_campaigns (name, product_id, created_at_utc) VALUES (?, ?, '2026-09-19')", (name, product_id))
    conn.commit()
    return cur.lastrowid

def insert_outreach_campaign(db_path, name):
    conn = db_connector.get_connection(db_path)
    cur = conn.execute("INSERT INTO campaigns (name, template, created_at_utc) VALUES (?, 'Template', '2026-09-19')", (name,))
    conn.commit()
    return cur.lastrowid


def test_legacy_regression(db_path):
    # A legacy prospect without research_campaign_id
    store = LeadStore(Path(db_path))
    lead = DiscoveredLead(
        domain="legacy.com",
        email="test@legacy.com",
        confidence_type="PERSONAL",
        email_confidence=100.0,
        source_type="test",
        engine="test",
        source_url="test",
        query="test",
        relevance_score=85.0,
        why_matched="Good fit"
    )
    store.save_lead(lead)
    
    # Approve prospect manually
    conn = db_connector.get_connection(db_path)
    conn.execute("UPDATE prospects SET status = 'approved', campaign_id = 1 WHERE business_email = 'test@legacy.com'")
    conn.commit()
    
    insert_outreach_campaign(db_path, "Legacy Campaign")
    
    outreach = OutreachDatabase(Path(db_path))
    approved = outreach.approved_for_campaign("Legacy Campaign", 10)
    assert len(approved) == 1, "Legacy prospect should be eligible"


def test_product_driven_eligibility(db_path, monkeypatch):
    store = LeadStore(Path(db_path))
    
    # Insert Product & Research Campaign
    product_profile = {
        "value_proposition": "AI CRM",
        "negative_keywords": ["plumbing"]
    }
    prod_id = insert_product(db_path, "Product A", json.dumps(product_profile))
    rc_id = insert_research_campaign(db_path, "RC A", prod_id)
    
    # Mock AI Provider
    class MockProvider:
        def __init__(self, *args, **kwargs):
            self.last_error = None
        def available(self): return True
        def generate_structured(self, system, user):
            if "Plumber" in user:
                return '{"fit_status": "NO_FIT", "fit_score": 10, "reason": "No fit", "evidence_source_ids": ["src1"]}'
            elif "MissingEv" in user:
                return '{"fit_status": "FIT", "fit_score": 90, "reason": "Fit", "evidence_source_ids": []}'
            return '{"fit_status": "FIT", "fit_score": 85, "reason": "Fit", "evidence_source_ids": ["src1"]}'
            
    import osint_engine.product_qualification
    monkeypatch.setattr(osint_engine.product_qualification, "get_ai_provider", lambda db: MockProvider())

    # Good Lead
    lead1 = DiscoveredLead(
        domain="good.com", email="good@good.com",
        confidence_type="PERSONAL", email_confidence=100.0, source_type="test", engine="test", source_url="test", query="test",
        relevance_score=85.0, why_matched="Good fit"
    )
    store.save_lead(lead1, research_campaign_id=rc_id)
    
    # Bad Lead (Negative Signal)
    lead2 = DiscoveredLead(
        domain="bad.com", email="bad@bad.com", company_name="Plumber",
        confidence_type="PERSONAL", email_confidence=100.0, source_type="test", engine="test", source_url="test", query="test",
        relevance_score=85.0, why_matched="Good fit"
    )
    store.save_lead(lead2, research_campaign_id=rc_id)
    
    conn = db_connector.get_connection(db_path)
    
    # Ensure they both still have P3 qualification_status = QUALIFIED
    p1 = conn.execute("SELECT qualification_status FROM prospects WHERE business_email='good@good.com'").fetchone()
    p2 = conn.execute("SELECT qualification_status FROM prospects WHERE business_email='bad@bad.com'").fetchone()
    assert p1[0] == 'QUALIFIED'
    assert p2[0] == 'QUALIFIED'
    
    # Check prospect_product_fit
    fit1 = conn.execute("SELECT fit_status, fit_score FROM prospect_product_fit WHERE prospect_id=1").fetchone()
    fit2 = conn.execute("SELECT fit_status, fit_score FROM prospect_product_fit WHERE prospect_id=2").fetchone()
    assert fit1[0] == 'FIT'
    assert fit1[1] == 85
    assert fit2[0] == 'NO_FIT'
    assert fit2[1] == 10
    
    # Sender Test
    out_camp_id = insert_outreach_campaign(db_path, "Outreach A")
    conn.execute("UPDATE prospects SET status = 'approved', campaign_id = ? WHERE business_email IN ('good@good.com', 'bad@bad.com')", (out_camp_id,))
    conn.commit()
    
    outreach = OutreachDatabase(Path(db_path))
    approved = outreach.approved_for_campaign("Outreach A", 10)
    assert len(approved) == 1
    assert approved[0]["business_email"] == "good@good.com"

def test_missing_evidence_returns_review_required(db_path, monkeypatch):
    store = LeadStore(Path(db_path))
    prod_id = insert_product(db_path, "Product A", "{}")
    rc_id = insert_research_campaign(db_path, "RC A", prod_id)
    
    class MockProviderNoEvidence:
        def __init__(self, *args, **kwargs):
            self.last_error = None
        def available(self): return True
        def generate_structured(self, system, user):
            return '{"fit_status": "FIT", "fit_score": 90, "reason": "Fit", "evidence_source_ids": []}'
            
    import osint_engine.product_qualification
    monkeypatch.setattr(osint_engine.product_qualification, "get_ai_provider", lambda db: MockProviderNoEvidence())

    lead1 = DiscoveredLead(
        domain="ev.com", email="ev@ev.com",
        confidence_type="PERSONAL", email_confidence=100.0, source_type="test", engine="test", source_url="test", query="test",
        relevance_score=85.0, why_matched="Good fit"
    )
    store.save_lead(lead1, research_campaign_id=rc_id)
    
    conn = db_connector.get_connection(db_path)
    fit = conn.execute("SELECT fit_status FROM prospect_product_fit").fetchone()
    # It must enforce REVIEW_REQUIRED if no evidence
    assert fit[0] == 'REVIEW_REQUIRED'

def test_multi_product_no_collision(db_path, monkeypatch):
    store = LeadStore(Path(db_path))
    
    prod_a = insert_product(db_path, "Product A", '{"name": "Product A"}')
    prod_b = insert_product(db_path, "Product B", '{"name": "Product B"}')
    rc_a = insert_research_campaign(db_path, "RC A", prod_a)
    rc_b = insert_research_campaign(db_path, "RC B", prod_b)
    
    class MockProviderMulti:
        def __init__(self, *args, **kwargs):
            self.last_error = None
        def available(self): return True
        def generate_structured(self, system, user):
            if "Product A" in user:
                return '{"fit_status": "FIT", "fit_score": 85, "reason": "Fit", "evidence_source_ids": ["src1"]}'
            return '{"fit_status": "NO_FIT", "fit_score": 10, "reason": "No fit", "evidence_source_ids": ["src1"]}'
            
    import osint_engine.product_qualification
    monkeypatch.setattr(osint_engine.product_qualification, "get_ai_provider", lambda db: MockProviderMulti())

    lead1 = DiscoveredLead(
        domain="multi.com", email="multi@multi.com", company_name="Multi Company",
        confidence_type="PERSONAL", email_confidence=100.0, source_type="test", engine="test", source_url="test", query="test",
        relevance_score=85.0, why_matched="Good fit"
    )
    
    # Save for RC A
    store.save_lead(lead1, research_campaign_id=rc_a)
    # Save for RC B (same lead, different RC/Product)
    store.save_lead(lead1, research_campaign_id=rc_b)
    
    conn = db_connector.get_connection(db_path)
    fits = conn.execute("SELECT product_id, fit_status FROM prospect_product_fit ORDER BY product_id").fetchall()
    
    assert len(fits) == 2
    assert fits[0][0] == prod_a
    assert fits[0][1] == 'FIT'
    assert fits[1][0] == prod_b
    assert fits[1][1] == 'NO_FIT'
    
    # Ensure qualification_status is still QUALIFIED globally
    qual = conn.execute("SELECT qualification_status FROM prospects WHERE business_email='multi@multi.com'").fetchone()
    assert qual[0] == 'QUALIFIED'
    
    # Outreach checks
    out_camp_a = insert_outreach_campaign(db_path, "Outreach A")
    out_camp_b = insert_outreach_campaign(db_path, "Outreach B")
    
    conn.execute("UPDATE prospects SET status = 'approved', campaign_id = ?, research_campaign_id = ? WHERE business_email='multi@multi.com'", (out_camp_a, rc_a))
    conn.commit()
    outreach = OutreachDatabase(Path(db_path))
    assert len(outreach.approved_for_campaign("Outreach A", 10)) == 1
    
    conn.execute("UPDATE prospects SET status = 'approved', campaign_id = ?, research_campaign_id = ? WHERE business_email='multi@multi.com'", (out_camp_b, rc_b))
    conn.commit()
    assert len(outreach.approved_for_campaign("Outreach B", 10)) == 0
