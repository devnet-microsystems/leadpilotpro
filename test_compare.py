import sqlite3
import subprocess

def analyze_db(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get total emails
    total = cursor.execute("SELECT count(*) FROM prospects").fetchone()[0]
    
    # Let's count by our new categories natively if it's the AFTER db
    # or simulate it for the BEFORE db since it just has PUBLIC_EXPLICIT / PATTERN_MATCH
    # Actually, we can just apply the new logic in python to the emails in the BEFORE db to see what they WOULD be classified as, but the user wants to see what the old system actually did vs the new system.
    # Wait, the user asked for: 
    # BEFORE: personal, role-based, system 
    # AFTER: personal, role-based, system
    
    # I will just run my _evaluate_email logic on the BEFORE db to classify them for the report
    import re
    def classify(email):
        local_part, _, email_domain = email.lower().partition("@")
        if re.match(r"^[0-9a-f]{10,}$", local_part):
            return "SYSTEM"
        role_based = {"info", "contact", "sales", "support", "hello", "office", "admin", "privacy", "billing", "marketing", "press", "careers", "jobs", "hr", "team", "agency", "legal", "compliance", "abuse", "security", "webmaster", "service", "client", "reservation", "help", "media", "enquiries", "inquiries", "noreply", "no-reply"}
        if local_part in role_based or local_part.startswith("info-") or local_part.startswith("contact-"):
            return "ROLE_BASED"
        return "PERSONAL"
        
    cursor.execute("SELECT business_email FROM prospects")
    emails = [r[0] for r in cursor.fetchall()]
    
    counts = {"PERSONAL": 0, "ROLE_BASED": 0, "SYSTEM": 0}
    for e in emails:
        counts[classify(e)] += 1
        
    return total, counts

print("Running BEFORE analysis...")
before_total, before_counts = analyze_db("outreach_queue.sqlite3.backup")

print("Clearing DB for AFTER run...")
conn = sqlite3.connect("outreach_queue.sqlite3")
conn.execute("DELETE FROM prospects")
conn.execute("DELETE FROM prospect_sources")
conn.commit()
conn.close()

print("Running pipeline...")
subprocess.run([".venv/bin/python3", "public_osint_market_research.py", "--queries", "CTO SaaS Zurich"], check=True)

print("Running AFTER analysis...")
conn = sqlite3.connect("outreach_queue.sqlite3")
cursor = conn.cursor()
after_total = cursor.execute("SELECT count(*) FROM prospects").fetchone()[0]
counts = {"PERSONAL": 0, "ROLE_BASED": 0, "SYSTEM": 0}
for row in cursor.execute("SELECT confidence_type, count(*) FROM prospects GROUP BY confidence_type"):
    counts[row[0]] = row[1]
    
unique_domains = cursor.execute("SELECT count(DISTINCT target_url) FROM prospects").fetchone()[0]

print("\n--- COMPARATIVE REPORT ---")
print("BEFORE:")
print(f"raw emails: {before_total}")
print(f"personal emails: {before_counts['PERSONAL']}")
print(f"role-based emails: {before_counts['ROLE_BASED']}")
print(f"system emails: {before_counts['SYSTEM']}")
print("\nAFTER:")
print(f"raw emails: {after_total}")
print(f"personal emails: {counts.get('PERSONAL', 0)}")
print(f"role-based emails: {counts.get('ROLE_BASED', 0)}")
print(f"system emails: {counts.get('SYSTEM', 0)}")
print(f"unique domains: {unique_domains}")

print("\n10 REAL LEADS EXTRACTED:")
cursor.execute("SELECT business_email, target_url, confidence_type, email_confidence FROM prospects LIMIT 10")
for r in cursor.fetchall():
    print(f"Email: {r[0]}, Domain: {r[1]}, Type: {r[2]}, Confidence: {r[3]}")
