import sqlite3
from datetime import datetime, timezone
import os

db_path = "outreach_queue.sqlite3"
conn = sqlite3.connect(db_path)

# Cleanup previous tests if any
conn.execute("DELETE FROM research_campaigns WHERE name = 'Test London Berlin MVP'")
conn.execute("DELETE FROM sales_offers WHERE name = 'Sviluppo MVP NextJS'")
conn.execute("DELETE FROM ideal_customer_profiles WHERE name = 'SaaS Founders London Berlin'")
conn.commit()

# Create Offer
conn.execute("""
    INSERT INTO sales_offers (name, description, created_at_utc)
    VALUES (?, ?, ?)
""", ("Sviluppo MVP NextJS", "Sviluppo di MVP web con Next.js, React e AI per startup e aziende SaaS.", datetime.now(timezone.utc).isoformat()))
offer_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

# Create ICP
conn.execute("""
    INSERT INTO ideal_customer_profiles (name, roles, industries, company_sizes, countries, languages, created_at_utc)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", ("SaaS Founders London Berlin", "Founder, Co-Founder, CEO, CTO", "SaaS, Software, Fintech", "1-50, 51-200", "UK, Germany", "en", datetime.now(timezone.utc).isoformat()))
icp_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

# Create Campaign
conn.execute("""
    INSERT INTO research_campaigns (name, offer_id, icp_id, created_at_utc)
    VALUES (?, ?, ?, ?)
""", ("Test London Berlin MVP", offer_id, icp_id, datetime.now(timezone.utc).isoformat()))
campaign_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

conn.commit()

import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from osint_engine.generator import QueryGenerator
gen = QueryGenerator(db_path)
gen.generate_templates_for_campaign(campaign_id)

print(f"Created Campaign ID: {campaign_id}")
