import sqlite3
import db_connector
import json
import time
from product_intelligence.campaign_builder import create_campaign_from_product
from osint_engine.quality import EmailValidator
from public_osint_market_research import LeadStore
from osint_engine.models import DiscoveredLead

def setup_db(db_path):
    conn = db_connector.get_connection(db_path)
    # Ensure fresh test products
    profile_a = {
        "product_name": "AI CRM",
        "keywords": ["AI CRM"],
        "target_company_types": ["SaaS companies"],
        "target_industries": ["Software"],
        "potential_buyer_roles": ["CEO", "VP Sales"],
        "negative_keywords": ["jobs"]
    }
    
    profile_b = {
        "product_name": "Cybersecurity Monitoring",
        "keywords": ["Cybersecurity"],
        "target_company_types": ["Banks"],
        "target_industries": ["Finance"],
        "potential_buyer_roles": ["CISO"],
    }
    
    c = conn.cursor()
    ts = int(time.time())
    
    c.execute("INSERT INTO products (name, slug, status, raw_summary, created_at_utc, updated_at_utc) VALUES (?, ?, 'READY', ?, datetime('now'), datetime('now'))",
              (f"AI CRM P5.2E {ts}", f"ai-crm-p52e-{ts}", json.dumps(profile_a)))
    prod_a = c.lastrowid
    
    c.execute("INSERT INTO products (name, slug, status, raw_summary, created_at_utc, updated_at_utc) VALUES (?, ?, 'READY', ?, datetime('now'), datetime('now'))",
              (f"Cybersecurity P5.2E {ts}", f"cybersecurity-p52e-{ts}", json.dumps(profile_b)))
    prod_b = c.lastrowid
    
    conn.commit()
    conn.close()
    return prod_a, prod_b

def main():
    print("=" * 50)
    print("P5.2E — PRODUCT-AWARE QUALIFICATION GATE")
    print("=" * 50)
    
    db_path = "outreach_queue.sqlite3"
    prod_a, prod_b = setup_db(db_path)
    
    print(f"\n[+] Created Test Products: {prod_a}, {prod_b}")
    
    # 1. Campaign Builder
    camp_a = create_campaign_from_product(db_path, prod_a)
    camp_b = create_campaign_from_product(db_path, prod_b)
    print(f"  - Campaign A ID: {camp_a}")
    print(f"  - Campaign B ID: {camp_b}")
    
    runner = LeadStore(db_path)
    
    # 2. Test Cases
    
    ts = int(time.time())
    # CASE 1: Legacy (no campaign, no product)
    print("\n[+] TEST: LEGACY LEAD")
    lead_legacy = DiscoveredLead(
        domain="legacy.com",
        company_name="Legacy Corp",
        email=f"ceo_{ts}@legacy.com",
        source_type="test",
        engine="test",
        source_url="test",
        query="test",
        email_confidence=0.99,
        confidence_type="PATTERN",
        relevance_score=80,
        why_matched="Test match"
    )
    runner.save_lead(lead_legacy, query_run_id="test1", research_campaign_id=None)
    
    conn = db_connector.get_connection(db_path)
    conn.row_factory = sqlite3.Row
    p_legacy = conn.execute("SELECT * FROM prospects WHERE business_email=?", (f"ceo_{ts}@legacy.com",)).fetchone()
    print(f"  - Qualification: {p_legacy['qualification_status']} (Expected: QUALIFIED)")
    if p_legacy['qualification_status'] == 'QUALIFIED':
        print("  ✅ LEGACY PRESERVATION: PASS")
    else:
        print("  ❌ LEGACY PRESERVATION: FAIL")
        
    # CASE 2: Product A FIT
    print("\n[+] TEST: PRODUCT A - FIT")
    lead_a_fit = DiscoveredLead(
        domain="saas.com",
        company_name="Cool SaaS Inc",
        email=f"vp_{ts}@saas.com",
        source_type="test",
        engine="test",
        source_url="test",
        query="test",
        email_confidence=0.99,
        confidence_type="PATTERN",
        relevance_score=85,
        why_matched="VP Sales at a Software SaaS company looking for AI CRM."
    )
    runner.save_lead(lead_a_fit, query_run_id="test2", research_campaign_id=camp_a)
    p_fit = conn.execute("SELECT * FROM prospects WHERE business_email=?", (f"vp_{ts}@saas.com",)).fetchone()
    print(f"  - Qualification: {p_fit['qualification_status']} (Expected: QUALIFIED)")
    
    fit_record = conn.execute("SELECT * FROM prospect_product_fit WHERE prospect_id=? AND product_id=?", (p_fit['id'], prod_a)).fetchone()
    if fit_record:
        print(f"  - Fit Status: {fit_record['fit_status']}")
        print(f"  - Fit Score: {fit_record['fit_score']}")
        print(f"  - Reason: {fit_record['reason']}")
    else:
        print("  ❌ MISSING FIT RECORD")
        
    # CASE 3: Product A NO_FIT
    print("\n[+] TEST: PRODUCT A - NO_FIT")
    lead_a_nofit = DiscoveredLead(
        domain="plumbing.com",
        company_name="Mario Plumbing",
        email=f"mario_{ts}@plumbing.com",
        source_type="test",
        engine="test",
        source_url="test",
        query="test",
        email_confidence=0.99,
        confidence_type="PATTERN",
        relevance_score=85,
        why_matched="Plumber offering toilet repair services. Also looking for jobs."
    )
    runner.save_lead(lead_a_nofit, query_run_id="test3", research_campaign_id=camp_a)
    p_nofit = conn.execute("SELECT * FROM prospects WHERE business_email=?", (f"mario_{ts}@plumbing.com",)).fetchone()
    print(f"  - Qualification: {p_nofit['qualification_status']} (Expected: UNQUALIFIED)")
    
    fit_record = conn.execute("SELECT * FROM prospect_product_fit WHERE prospect_id=? AND product_id=?", (p_nofit['id'], prod_a)).fetchone()
    if fit_record:
        print(f"  - Fit Status: {fit_record['fit_status']}")
        print(f"  - Reason: {fit_record['reason']}")
        
    # CASE 4: Product B with same NO_FIT prospect (Idempotency / Multi-product)
    print("\n[+] TEST: MULTI-PRODUCT IDEMPOTENCY")
    lead_b_nofit = DiscoveredLead(
        domain="plumbing.com",
        company_name="Mario Plumbing",
        email=f"mario_{ts}@plumbing.com",
        source_type="test",
        engine="test",
        source_url="test",
        query="test",
        email_confidence=0.99,
        confidence_type="PATTERN",
        relevance_score=85,
        why_matched="Plumber offering toilet repair services."
    )
    runner.save_lead(lead_b_nofit, query_run_id="test4", research_campaign_id=camp_b)
    p_nofit_b = conn.execute("SELECT * FROM prospects WHERE business_email=?", (f"mario_{ts}@plumbing.com",)).fetchone()
    print(f"  - Qualification: {p_nofit_b['qualification_status']} (Expected: UNQUALIFIED)")
    
    count_fits = conn.execute("SELECT COUNT(*) FROM prospect_product_fit WHERE prospect_id=?", (p_nofit_b['id'],)).fetchone()[0]
    print(f"  - Number of fit records for prospect: {count_fits} (Expected: 2)")
    
    conn.close()

if __name__ == "__main__":
    main()
