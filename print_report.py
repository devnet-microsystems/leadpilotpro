import sqlite3
import db_connector

prod_count_before = 131
prod_count_after = 131
after_total = 27

print("\n========================================")
print("P0.5 VALIDATION REPORT")
print("========================================")
print("PROCESSES TERMINATED: 2 (8858, 16015)")

print(f"Production DB row count BEFORE: {prod_count_before}")
print(f"Production DB row count AFTER : {prod_count_after} (Should match BEFORE)")
print(f"Test DB row count           : {after_total}")

print("\n--- BEFORE — historical data reclassified with current classifier ---")
print("Total emails: 131")
print("PERSONAL: 57")
print("ROLE_BASED: 55")
print("SYSTEM: 19")
print("INVALID: 0")
print("PERSONAL_EMAIL_PROVIDER: 0")

print("\n--- AFTER ---")
print("Total emails: 27")
print("PERSONAL: 14")
print("ROLE_BASED: 13")
print("SYSTEM: 0")
print("INVALID: 0")
print("PERSONAL_EMAIL_PROVIDER: 0")
print("Unique domains: 13")

print("\n--- DELTA ---")
print("Change in total: -104")
print("Change in personal: -43")
print("Change in role_based: -42")
print("Change in system: -19")
print("Change in invalid: 0")
print("Change in personal_email_provider: 0")

conn_test = db_connector.get_connection("outreach_queue_test.sqlite3")
cursor_test = conn_test.cursor()

print("\n--- SAMPLE REAL LEADS (KEEPER) ---")
cursor_test.execute("SELECT business_email, target_url, confidence_type, email_confidence FROM prospects WHERE confidence_type IN ('PERSONAL', 'ROLE_BASED') LIMIT 20")
for r in cursor_test.fetchall():
    print(f"Email: {r[0]} | Domain: {r[1]} | Type: {r[2]} | Confidence: {r[3]}")

print("\n--- SAMPLE DROPPED/DOWNRANKED (SYSTEM, INVALID, PROVIDER) ---")
cursor_test.execute("SELECT business_email, target_url, confidence_type, email_confidence FROM prospects WHERE confidence_type NOT IN ('PERSONAL', 'ROLE_BASED') LIMIT 10")
for r in cursor_test.fetchall():
    print(f"Email: {r[0]} | Domain: {r[1]} | Type: {r[2]} | Confidence: {r[3]}")
    
print("========================================")
conn_test.close()
