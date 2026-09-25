import os
import sqlite3
import json

db_path = "leadpilot.db"
conn = sqlite3.connect(db_path)
offers = conn.execute("SELECT * FROM sales_offers").fetchall()
icps = conn.execute("SELECT * FROM ideal_customer_profiles").fetchall()
print(f"In leadpilot.db - Offers: {len(offers)}, ICPs: {len(icps)}")

db_path = "outreach_queue.sqlite3"
conn = sqlite3.connect(db_path)
offers = conn.execute("SELECT * FROM sales_offers").fetchall()
icps = conn.execute("SELECT * FROM ideal_customer_profiles").fetchall()
print(f"In outreach_queue.sqlite3 - Offers: {len(offers)}, ICPs: {len(icps)}")

