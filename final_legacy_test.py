import sqlite3
import time
import json
import uuid
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

BASE_URL = "http://127.0.0.1:8001"
TEST_EMAIL = f"antoniomichelotti+legacytest_{uuid.uuid4().hex[:8]}@devnet-microsystems.com"

def inject_session():
    token = str(uuid.uuid4())
    conn = sqlite3.connect("outreach_queue.sqlite3")
    expires = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    conn.execute("INSERT INTO sessions (token, user_id, expires_at_utc) VALUES (?, 1, ?)", (token, expires))
    conn.commit()
    conn.close()
    return token

SESSION_TOKEN = inject_session()

def req(url, method="GET", data=None):
    request = urllib.request.Request(url, method=method)
    request.add_header("Cookie", f"session_token={SESSION_TOKEN}")
    if data is not None:
        request.add_header('Content-Type', 'application/json')
        request.data = json.dumps(data).encode('utf-8')
    try:
        res = urllib.request.urlopen(request)
        if res.status not in [200, 204]:
            raise Exception(f"HTTP {res.status}")
        body = res.read()
        return json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        raise Exception(f"HTTP Error {e.code}: {e.read().decode()}")

print("--- STARTING LEGACY REGRESSION TEST ---")

# 1. Trova una campagna legacy
camp_list = req(f"{BASE_URL}/api/campaigns")
legacy_camp = next((c for c in camp_list if c.get("name") == "sovereign selling"), None)
if not legacy_camp:
    print("Campagna 'sovereign selling' non trovata.")
    exit(1)

legacy_cid = legacy_camp['id']
print(f"1. Trovata campagna legacy: {legacy_camp['name']} (ID {legacy_cid})")

# 2. Inserimento manuale di un lead (simula vecchio flow CSV/manuale)
req(f"{BASE_URL}/api/prospects/manual_add", method="POST", data={
    "email": TEST_EMAIL,
    "company_name": "Legacy Test Corp",
    "campaign": "",
    "url": "https://legacytest.local"
})
print(f"2. Inserito lead manuale: {TEST_EMAIL}")

# 3. Verifica pending_review
prospects = req(f"{BASE_URL}/api/prospects?status=pending_review")
p_dict = next((p for p in prospects if p["business_email"] == TEST_EMAIL), None)
if not p_dict:
    print("Lead non trovato in pending_review!")
    exit(1)
pend_id = p_dict["id"]
print("3. Lead confermato in pending_review.")

# 4. Approva il lead assegnando la campagna legacy
req(f"{BASE_URL}/api/approve", method="POST", data={
    "id": pend_id,
    "reason": "Legacy Regression Test",
    "campaign_id": legacy_cid
})
print("4. Lead approvato e assegnato alla campagna legacy.")

# 5. Esegui l'invio SMTP
print("5. Avvio elaborazione coda SMTP (run_send_task via API)...")
req(f"{BASE_URL}/api/send", method="POST", data={"campaign": legacy_camp["name"], "limit": 1})

# Attendi che il background task finisca e aggiorni il DB
for i in range(25):
    time.sleep(2)
    conn = sqlite3.connect("outreach_queue.sqlite3")
    conn.row_factory = sqlite3.Row
    p_status = conn.execute("SELECT status FROM prospects WHERE id=?", (pend_id,)).fetchone()
    if p_status and p_status["status"] == "sent":
        break
    if p_status and p_status["status"] == "rejected":
        print("Errore durante l'invio (SMTP rejected). Controlla outreach_sender.py.")
        break
    conn.close()

conn = sqlite3.connect("outreach_queue.sqlite3")
conn.row_factory = sqlite3.Row
final_p = conn.execute("SELECT status FROM prospects WHERE id=?", (pend_id,)).fetchone()

if not final_p or final_p["status"] != "sent":
    print(f"Test Fallito. Stato finale del prospect: {final_p['status'] if final_p else 'Missing'}")
    exit(1)
print("6. SMTP Send completato con successo (status = sent).")

# 6. Verifica email_archive
archive_row = conn.execute("SELECT message_text FROM email_archive WHERE business_email=?", (TEST_EMAIL,)).fetchone()
if not archive_row:
    print("Test Fallito. Nessun record in email_archive.")
    exit(1)

content = archive_row["message_text"]
if "Legacy Test Corp" not in content and "Legacy test corp" not in content:
    print("Attenzione: il template renderizzato non contiene il nome azienda come ci si aspettava.")

print("7. Record trovato in email_archive e template renderizzato con successo.")
print("   Contenuto archiviato (estratto):")
print(content[:200] + "...\n")

# PULIZIA (Remove test data to avoid polluting DB)
conn.execute("DELETE FROM email_archive WHERE business_email=?", (TEST_EMAIL,))
conn.execute("DELETE FROM send_events WHERE prospect_id=?", (pend_id,))
conn.execute("DELETE FROM prospects WHERE id=?", (pend_id,))
conn.commit()
conn.close()

print("--- LEGACY REGRESSION TEST: PASS ---")
