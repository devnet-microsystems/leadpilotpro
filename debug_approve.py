import urllib.request
import json
import uuid

BASE_URL = "http://127.0.0.1:8001"

import sqlite3
from datetime import datetime, timedelta, timezone

conn = sqlite3.connect("outreach_queue.sqlite3")
conn.execute("UPDATE prospects SET status='pending_review' WHERE id=164")
conn.commit()

def inject_session():
    token = str(uuid.uuid4())
    expires = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    conn.execute("INSERT INTO sessions (token, user_id, expires_at_utc) VALUES (?, 1, ?)", (token, expires))
    conn.commit()
    return token

tok = inject_session()
request = urllib.request.Request(f"{BASE_URL}/api/approve", method="POST")
request.add_header("Cookie", f"session_token={tok}")
request.add_header('Content-Type', 'application/json')
request.data = json.dumps({"id": 164, "reason": "Test", "campaign_id": 1}).encode('utf-8')
try:
    res = urllib.request.urlopen(request)
    print(res.status, res.read().decode())
except Exception as e:
    print(e.code, e.read().decode())

print("After approve:", conn.execute("SELECT campaign_id, status FROM prospects WHERE id=164").fetchone())
conn.close()
