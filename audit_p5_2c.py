import sqlite3
import db_connector
import json
import time
from product_intelligence.campaign_builder import create_campaign_from_product

def setup_db(db_path):
    conn = db_connector.get_connection(db_path)
    # Ensure fresh test product
    profile = {
        "product_name": "AI CRM",
        "short_description": "B2B AI CRM",
        "target_company_types": ["SaaS companies", "software agencies"],
        "target_industries": ["Software", "Technology"],
        "potential_buyer_roles": ["CEO", "VP Sales"],
        "use_cases": ["sales automation"],
        "keywords": ["AI CRM", "sales automation"],
        "negative_keywords": ["jobs", "support"],
        "geographic_markets": ["Italy", "Spain", "United States"],
        "supported_languages": ["Italian", "Spanish", "English"]
    }
    
    # Check if a product with this specific test context exists
    c = conn.cursor()
    ts = int(time.time())
    c.execute("INSERT INTO products (name, slug, status, raw_summary, created_at_utc, updated_at_utc) VALUES (?, ?, 'READY', ?, datetime('now'), datetime('now'))",
              (f"AI CRM MultiMarket Test {ts}", f"ai-crm-multimarket-test-{ts}", json.dumps(profile)))
    prod_id = c.lastrowid
    conn.commit()
    conn.close()
    return prod_id

def main():
    print("=" * 50)
    print("P5.2C — PRODUCT → ICP + MARKETS + LANGUAGES")
    print("=" * 50)
    
    db_path = "outreach_queue.sqlite3"
    prod_id = setup_db(db_path)
    print(f"\n[+] Created Test Product ID: {prod_id}")
    
    # 1. Campaign Builder Pass 1
    camp1 = create_campaign_from_product(db_path, prod_id)
    print(f"\n[+] CAMPAIGN CREATION")
    print(f"  - First run campaign ID: {camp1}")
    
    # 2. Campaign Builder Pass 2
    camp2 = create_campaign_from_product(db_path, prod_id)
    print(f"  - Second run campaign ID: {camp2}")
    
    if camp1 == camp2:
        print("  ✅ IDEMPOTENCY: PASS")
    else:
        print("  ❌ IDEMPOTENCY: FAIL")
        
    conn = db_connector.get_connection(db_path)
    conn.row_factory = sqlite3.Row
    
    # Check ICP
    camp_row = conn.execute("SELECT * FROM research_campaigns WHERE id=?", (camp1,)).fetchone()
    icp = conn.execute("SELECT * FROM ideal_customer_profiles WHERE id=?", (camp_row["icp_id"],)).fetchone()
    
    print(f"\n[+] PRODUCT -> ICP MAPPING")
    print(f"  - roles: {icp['roles']}")
    print(f"  - industries: {icp['industries']}")
    print(f"  - countries (markets): {icp['countries']}")
    print(f"  - languages: {icp['languages']}")
    
    # Check Queries
    queries = conn.execute("SELECT * FROM campaign_queries WHERE campaign_id=?", (camp1,)).fetchall()
    print(f"\n[+] QUERY GENERATION")
    print(f"  - Total queries generated: {len(queries)}")
    for q in queries:
        print(f"  - Query: {q['query']}")
        
    # Check Templates
    templates = conn.execute("SELECT * FROM query_templates WHERE campaign_id=?", (camp1,)).fetchall()
    print(f"\n[+] TEMPLATES GENERATED: {len(templates)}")
    
    print("\n[+] REAL OSINT TRIGGER")
    print(f"  - Running public_osint_market_research.py for campaign {camp1}...")
    
    import subprocess
    result = subprocess.run([
        ".venv/bin/python", "public_osint_market_research.py",
        "--campaign-id", str(camp1),
        "--results-per-query", "2", # keep it small
        "--max-leads", "5"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("  ✅ OSINT Trigger ran successfully")
    else:
        print("  ❌ OSINT Trigger failed")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        
    # Check query runs
    runs = conn.execute("SELECT * FROM query_runs WHERE campaign_id=?", (camp1,)).fetchall()
    print(f"\n[+] REAL QUERY_RUN VERIFICATION")
    print(f"  - Runs found: {len(runs)}")
    for r in runs:
        print(f"  - Run {r['id']}: status={r['status']}, provider={r['provider']}, emails_found={r['emails_found']}, q={r['query']}")
        
    prospects = conn.execute("SELECT * FROM prospects WHERE research_campaign_id=?", (camp1,)).fetchall()
    print(f"\n[+] REAL DISCOVERY & P3 VERIFICATION")
    print(f"  - Prospects found: {len(prospects)}")
    
    conn.close()

if __name__ == "__main__":
    main()
