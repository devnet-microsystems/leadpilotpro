import sqlite3
import json
import time
from product_intelligence.campaign_builder import create_campaign_from_product
from osint_engine.generator import QueryGenerator

import logging

logging.basicConfig(level=logging.INFO)

DB_PATH = "outreach_queue.sqlite3"

def run_audit():
    print("==================================================")
    print("P5.2A — REAL PRODUCT → ICP → MARKET → OSINT AUDIT")
    print("==================================================")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # 1. Create a comprehensive Product Profile
    profile = {
        "product_name": "Audit CRM Pro",
        "category": "Software",
        "keywords": ["AI CRM", "sales automation"],
        "negative_keywords": ["jobs", "support"],
        "potential_buyer_roles": ["CEO", "VP Sales"],
        "target_company_types": ["SaaS companies"],
        "target_industries": ["Software"],
        "geographic_markets": ["Italy", "Spain", "United States"],
        "supported_languages": ["Italian", "Spanish", "English"],
        "pricing_information": {"status": "KNOWN", "summary": "$500/mo"}
    }
    
    conn.execute(
        "INSERT INTO products (name, slug, status, created_at_utc, updated_at_utc, raw_summary) VALUES (?, ?, ?, 'now', 'now', ?)",
        ("Audit CRM Pro", f"audit-crm-{int(time.time())}", "READY", json.dumps(profile))
    )
    product_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    
    print(f"\n[+] Created Test Product ID: {product_id}")
    
    # 2. Campaign Creation & Idempotency
    camp1 = create_campaign_from_product(DB_PATH, product_id)
    time.sleep(1)
    camp2 = create_campaign_from_product(DB_PATH, product_id)
    
    print(f"\n[+] CAMPAIGN CREATION")
    print(f"  - First run campaign ID: {camp1}")
    print(f"  - Second run campaign ID: {camp2}")
    
    if camp1 != camp2:
        print("  ❌ IDEMPOTENCY: FAILED (Duplicates created)")
    else:
        print("  ✅ IDEMPOTENCY: PASS")
        
    # 3. Product -> ICP & Market mapping
    camp_row = conn.execute("SELECT * FROM research_campaigns WHERE id=?", (camp1,)).fetchone()
    icp = conn.execute("SELECT * FROM ideal_customer_profiles WHERE id=?", (camp_row["icp_id"],)).fetchone()
    
    print(f"\n[+] PRODUCT -> ICP MAPPING")
    print(f"  - roles: {icp['roles']}")
    print(f"  - industries: {icp['industries']}")
    print(f"  - countries (markets): {icp['countries']}")
    
    # 4. Query Generation
    gen = QueryGenerator(DB_PATH)
    queries = gen.get_concrete_queries(camp1)
    print(f"\n[+] QUERY GENERATION")
    print(f"  - Total queries generated: {len(queries)}")
    for q in queries[:5]:
        print(f"  - Query: {q['query']}")
        if "UNKNOWN" in q['query'] or '""' in q['query']:
            print("  ❌ QUERY QUALITY: FAILED (Empty/UNKNOWN strings detected)")
            
    # Check negative keywords
    print("\n[+] NEGATIVE KEYWORDS")
    print(f"  - Profile has: {profile['negative_keywords']}")
    
    # 5. OSINT Trigger
    print("\n[+] REAL OSINT TRIGGER")
    print(f"  - Running public_osint_market_research.py for campaign {camp1}...")
    import subprocess
    result = subprocess.run([
        ".venv/bin/python", "public_osint_market_research.py",
        "--campaign-id", str(camp1),
        "--max-queries", "1"
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        print("  ❌ OSINT Trigger failed")
        print("STDERR:", result.stderr)
    else:
        print("  ✅ OSINT Trigger ran successfully")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        
    # 6. Verify Results
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    runs = conn.execute("SELECT * FROM query_runs WHERE campaign_id=?", (camp1,)).fetchall()
    print(f"\n[+] REAL QUERY_RUN VERIFICATION")
    print(f"  - Runs found: {len(runs)}")
    for r in runs:
        print(f"  - Run {r['id']}: status={r['status']}, provider={r['provider']}, emails_found={r['emails_found']}")
        
    prospects = conn.execute("SELECT * FROM prospects WHERE research_campaign_id=?", (camp1,)).fetchall()
    print(f"\n[+] REAL DISCOVERY & P3 VERIFICATION")
    print(f"  - Prospects found: {len(prospects)}")
    for p in prospects:
        print(f"  - Prospect {p['business_email']}: qual_status={p.get('qualification_status', 'N/A')}, rel_score={p.get('relevance_score', 'N/A')}")
        
    conn.close()

if __name__ == "__main__":
    run_audit()
