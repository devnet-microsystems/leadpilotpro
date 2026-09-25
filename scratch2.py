import os
import sqlite3
import db_connector
import json

db_path = "leadpilot.db"
conn = db_connector.get_connection(db_path)
offers = conn.execute("SELECT * FROM sales_offers").fetchall()
icps = conn.execute("SELECT * FROM ideal_customer_profiles").fetchall()
print(f"In leadpilot.db - Offers: {len(offers)}, ICPs: {len(icps)}")

db_path = "outreach_queue.sqlite3"
conn = db_connector.get_connection(db_path)
offers = conn.execute("SELECT * FROM sales_offers").fetchall()
icps = conn.execute("SELECT * FROM ideal_customer_profiles").fetchall()
print(f"In outreach_queue.sqlite3 - Offers: {len(offers)}, ICPs: {len(icps)}")

