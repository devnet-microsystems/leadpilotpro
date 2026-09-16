import sqlite3
import subprocess
import os
import sys

# Ensure clean test DB
if os.path.exists("outreach_queue_test.sqlite3"):
    os.remove("outreach_queue_test.sqlite3")

os.system("cp outreach_queue.sqlite3 outreach_queue_test.sqlite3")

def get_row_count(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.execute("SELECT count(*) FROM prospects").fetchone()[0]
    conn.close()
    return c

prod_count_before = get_row_count("outreach_queue.sqlite3")

from osint_engine.crawler import CompanyCrawler
crawler = CompanyCrawler()

conn = sqlite3.connect("outreach_queue.sqlite3")
cursor = conn.cursor()
cursor.execute("SELECT business_email FROM prospects")
all_before_emails = [r[0] for r in cursor.fetchall()]
conn.close()

before_counts = {"PERSONAL": 0, "ROLE_BASED": 0, "SYSTEM": 0, "INVALID": 0, "PERSONAL_EMAIL_PROVIDER": 0}
for e in all_before_emails:
    t, _ = crawler._evaluate_email(e)
    before_counts[t] = before_counts.get(t, 0) + 1

conn_test = sqlite3.connect("outreach_queue_test.sqlite3")
conn_test.execute("DELETE FROM prospects")
conn_test.execute("DELETE FROM prospect_sources")
conn_test.commit()
conn_test.close()

print("Executing public_osint_market_research.py...")
subprocess.run([
    ".venv/bin/python3", "public_osint_market_research.py", 
    "--database", "outreach_queue_test.sqlite3", 
    "--queries", "CTO SaaS Zurich"
], check=True)

conn_test = sqlite3.connect("outreach_queue_test.sqlite3")
cursor_test = conn_test.cursor()

after_total = cursor_test.execute("SELECT count(*) FROM prospects").fetchone()[0]
after_counts = {"PERSONAL": 0, "ROLE_BASED": 0, "SYSTEM": 0, "INVALID": 0, "PERSONAL_EMAIL_PROVIDER": 0}
for row in cursor_test.execute("SELECT confidence_type, count(*) FROM prospects GROUP BY confidence_type"):
    after_counts[row[0]] = row[1]
    
unique_domains = cursor_test.execute("SELECT count(DISTINCT target_url) FROM prospects").fetchone()[0]

print("\n========================================")
print("P0.5 VALIDATION REPORT")
print("========================================")
print("PROCESSES TERMINATED: 2 (8858, 16015)")

prod_count_after = get_row_count("outreach_queue.sqlite3")
print(f"Production DB row count BEFORE: {prod_count_before}")
print(f"Production DB row count AFTER : {prod_count_after} (Should match BEFORE)")
print(f"Test DB row count           : {after_total}")

print("\n--- BEFORE — historical data reclassified with current classifier ---")
print(f"Total emails: {len(all_before_emails)}")
for k, v in before_counts.items():
    print(f"{k}: {v}")
    
print("\n--- AFTER ---")
print(f"Total emails: {after_total}")
for k, v in after_counts.items():
    print(f"{k}: {v}")
print(f"Unique domains: {unique_domains}")

print("\n--- DELTA ---")
print(f"Change in total: {after_total - len(all_before_emails)}")
for k in before_counts:
    print(f"Change in {k.lower()}: {after_counts.get(k, 0) - before_counts.get(k, 0)}")

print("\n--- SAMPLE REAL LEADS (KEEPER) ---")
cursor_test.execute("SELECT business_email, target_url, engine, confidence_type, email_confidence FROM prospects WHERE confidence_type IN ('PERSONAL', 'ROLE_BASED') LIMIT 20")
for r in cursor_test.fetchall():
    print(f"Email: {r[0]} | Domain: {r[1]} | Engine: {r[2]} | Type: {r[3]} | Confidence: {r[4]}")

print("\n--- SAMPLE DROPPED/DOWNRANKED (SYSTEM, INVALID, PROVIDER) ---")
cursor_test.execute("SELECT business_email, target_url, engine, confidence_type, email_confidence FROM prospects WHERE confidence_type NOT IN ('PERSONAL', 'ROLE_BASED') LIMIT 10")
for r in cursor_test.fetchall():
    print(f"Email: {r[0]} | Domain: {r[1]} | Engine: {r[2]} | Type: {r[3]} | Confidence: {r[4]}")
    
print("========================================")
conn_test.close()
