import sqlite3
import json
import time
from product_intelligence.campaign_builder import create_campaign_from_product

def setup_db(db_path):
    conn = sqlite3.connect(db_path)
    # Ensure fresh test product
    profile = {
        "product_name": "AI CRM",
        "keywords": [
            "AI CRM",
            "sales automation"
        ],
        "target_company_types": [
            "SaaS companies",
            "software agencies"
        ],
        "target_industries": [
            "Software",
            "Technology"
        ],
        "potential_buyer_roles": [
            "CEO",
            "VP Sales",
            "CRO"
        ],
        "geographic_markets": [
            "Italy",
            "Spain",
            "United States"
        ],
        "negative_keywords": [
            "jobs",
            "careers",
            "support",
            "login"
        ]
    }
    
    c = conn.cursor()
    ts = int(time.time())
    c.execute("INSERT INTO products (name, slug, status, raw_summary, created_at_utc, updated_at_utc) VALUES (?, ?, 'READY', ?, datetime('now'), datetime('now'))",
              (f"AI CRM Cap Test {ts}", f"ai-crm-cap-test-{ts}", json.dumps(profile)))
    prod_id = c.lastrowid
    conn.commit()
    conn.close()
    return prod_id

def main():
    print("=" * 50)
    print("P5.2D — QUERY EXPLOSION CONTROL + NEGATIVE KEYWORDS")
    print("=" * 50)
    
    db_path = "outreach_queue.sqlite3"
    prod_id = setup_db(db_path)
    print(f"\n[+] Created Test Product ID: {prod_id}")
    
    # 1. Campaign Builder Pass
    camp1 = create_campaign_from_product(db_path, prod_id)
    print(f"\n[+] CAMPAIGN CREATION")
    print(f"  - Campaign ID: {camp1}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Check Templates
    templates = conn.execute("SELECT * FROM query_templates WHERE campaign_id=?", (camp1,)).fetchall()
    
    # Check Queries
    queries = conn.execute("SELECT * FROM campaign_queries WHERE campaign_id=?", (camp1,)).fetchall()
    print(f"\n[+] QUERY GENERATION")
    print(f"  - RAW CANDIDATES (approx from templates x roles): {len(templates) * 3}")
    print(f"  - SELECTED QUERIES: {len(queries)}")
    
    markets_covered = set()
    roles_covered = set()
    keywords_covered = set()
    
    for q in queries:
        text = q['query']
        print(f"  - Query: {text}")
        
        # Check markets
        for m in ["Italy", "Spain", "United States"]:
            if m in text: markets_covered.add(m)
            
        # Check roles
        for r in ["CEO", "VP Sales", "CRO"]:
            if r in text: roles_covered.add(r)
            
        # Check keywords
        for k in ["AI CRM", "sales automation"]:
            if k in text: keywords_covered.add(k)
            
    print(f"\n[+] COVERAGE")
    print(f"  - Markets covered: {markets_covered}")
    print(f"  - Roles covered: {roles_covered}")
    print(f"  - Keywords covered: {keywords_covered}")
    
    if len(queries) <= 24:
        print("  ✅ CAP: PASS")
    else:
        print("  ❌ CAP: FAIL")
        
    print("\n[+] REAL OSINT TRIGGER")
    print(f"  - Running public_osint_market_research.py for campaign {camp1}...")
    
    import subprocess
    result = subprocess.run([
        ".venv/bin/python", "public_osint_market_research.py",
        "--campaign-id", str(camp1),
        "--results-per-query", "2",
        "--max-leads", "5",
        "--max-queries", "3" # Only run first 3 queries for the real small test
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
