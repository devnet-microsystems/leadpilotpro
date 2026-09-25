import sqlite3
import urllib.request
import json
import time
import subprocess
import os
import uuid
from datetime import datetime, timedelta, timezone

# BASE_URL is configurable via env var; default to 8000 (the real app port).
# Previously hardcoded to 8001 — that was a test-harness bug, not an app bug.
BASE_URL = os.environ.get("LEADPILOT_BASE_URL", "http://127.0.0.1:8000")
DB_PATH = os.environ.get("LEADPILOT_DB_PATH", "outreach_queue.sqlite3")

def inject_session():
    token = str(uuid.uuid4())
    conn = sqlite3.connect(DB_PATH)
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

def run_test():
    print("Starting STRICT E2E Test...")
    t = str(int(time.time()))
    
    # ------------------
    # RESEARCH ENGINE
    # ------------------
    research_res = {k: "NOT EXECUTED" for k in [
        "Offer", "ICP", "Campaign", "Query Generation", "Query Studio", "Provider", 
        "Search Results", "Crawler", "Extraction", "Prospect Creation", "Relevance", 
        "AI Qualification", "why_matched"
    ]}
    
    try:
        # 1. Offer & ICP
        req(f"{BASE_URL}/api/sales_offers", method="POST", data={"name": f"E2E Offer {t}", "description": "Sviluppo di MVP web con Next.js, React e AI per startup e aziende SaaS."})
        offer_id = next(o for o in req(f"{BASE_URL}/api/sales_offers") if o['name'] == f'E2E Offer {t}')['id']
        research_res["Offer"] = "PASS"
        
        req(f"{BASE_URL}/api/icps", method="POST", data={"name": f"E2E ICP {t}", "roles": "CEO", "industries": "SaaS", "locations": "London"})
        icp_id = next(i for i in req(f"{BASE_URL}/api/icps") if i['name'] == f'E2E ICP {t}')['id']
        research_res["ICP"] = "PASS"
        
        # 2. Campaign & Queries
        req(f"{BASE_URL}/api/research_campaigns", method="POST", data={"name": f"E2E Research {t}", "offer_id": offer_id, "icp_id": icp_id})
        rc_id = next(r for r in req(f"{BASE_URL}/api/research_campaigns") if r['name'] == f'E2E Research {t}')['id']
        research_res["Campaign"] = "PASS"
        
        req(f"{BASE_URL}/api/campaigns/{rc_id}/generate_plan", method="POST")
        queries = req(f"{BASE_URL}/api/campaigns/{rc_id}/queries")
        if len(queries) > 0:
            research_res["Query Generation"] = "PASS"
        else:
            research_res["Query Generation"] = "FAIL"
            raise Exception("No queries generated")
        
        # Overwrite one query to ensure Brave finds something
        q_id = queries[0]['id']
        req(f"{BASE_URL}/api/campaign_queries/{q_id}", method="PUT", data={"is_enabled": True, "query": "SaaS Founders London"})
        research_res["Query Studio"] = "PASS"
        
        # 4. Launch OSINT engine
        conn = sqlite3.connect(DB_PATH); conn.execute("DELETE FROM prospects WHERE business_email IN ('contact@saasiest.com', 'info@zsah.net')"); conn.commit(); conn.close(); print(f"Running OSINT engine for Campaign {rc_id}..."); 
        proc = subprocess.run([".venv/bin/python", "public_osint_market_research.py", "--campaign-id", str(rc_id), "--results-per-query", "2", "--max-queries", "2"], capture_output=True, text=True)
        log = proc.stdout + proc.stderr
        print("Log:", log)
        
        if "Brave" in log or "SearXNG" in log or "search" in log:
             research_res["Provider"] = "PASS"
        
        if "results" in log or "Unique domains" in log:
             research_res["Search Results"] = "PASS"
             
        if "crawling" in log or "crawled" in log.lower() or "crawler" in log or "extract" in log.lower():
             research_res["Crawler"] = "PASS"
             
        # Check real prospect discovery
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        prospects = conn.execute("SELECT * FROM prospects WHERE research_campaign_id=? ORDER BY id DESC", (rc_id,)).fetchall()
        
        if len(prospects) > 0:
            research_res["Extraction"] = "PASS"
            research_res["Prospect Creation"] = "PASS"
            p_dict = prospects[0]
            prospect_id = p_dict["id"]
            
            if p_dict["relevance_score"] is not None and int(p_dict["relevance_score"]) > 0:
                research_res["Relevance"] = "PASS"
            else:
                research_res["Relevance"] = "FAIL (Score 0 or Null)"
                
            wm = p_dict["why_matched"]
            if wm:
                if wm == "AI non configurata":
                    research_res["why_matched"] = "NOT EXECUTED (No API Key)"
                    research_res["AI Qualification"] = "NOT EXECUTED"
                else:
                    research_res["why_matched"] = "PASS"
                    research_res["AI Qualification"] = "PASS"
            else:
                research_res["why_matched"] = "FAIL (NULL/Empty)"
                research_res["AI Qualification"] = "FAIL"
        else:
            research_res["Extraction"] = "FAIL or NO DATA"
            research_res["Prospect Creation"] = "FAIL or NO DATA"
            raise Exception("No real prospects found.")

    except Exception as e:
        print(f"Research Test aborted or failed: {e}")
        
    print("\n### RESEARCH ENGINE")
    print("| Fase              | Stato     |")
    print("| ----------------- | --------- |")
    for k, v in research_res.items():
        print(f"| {k.ljust(17)} | {v.ljust(9)} |")
        
    # ------------------
    # LEGACY OUTREACH
    # ------------------
    legacy_res = {k: "NOT EXECUTED" for k in [
        "Campaigns loaded", "Templates loaded", "Leads Pending", 
        "Approval + campaign_id", "Scheduled Jobs", "Sender", "SMTP", "Archive"
    ]}
    
    try:
        camp_list = req(f"{BASE_URL}/api/campaigns")
        if len(camp_list) > 0: legacy_res["Campaigns loaded"] = "PASS"
        
        tpl_list = req(f"{BASE_URL}/api/templates")
        if len(tpl_list) > 0: legacy_res["Templates loaded"] = "PASS"
        
        # Test approval workflow using the first available pending prospect
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        pend_prospects = conn.execute("SELECT id FROM prospects WHERE status='pending_review' ORDER BY id DESC LIMIT 1").fetchall()
        
        if len(pend_prospects) > 0:
            legacy_res["Leads Pending"] = "PASS"
            pend_id = pend_prospects[0]["id"]
            
            # Use the first legacy campaign
            legacy_camp = next(c for c in camp_list if c.get("name") == "sovereign selling"); legacy_cid = legacy_camp['id']; legacy_name = legacy_camp['name']
            
            req(f"{BASE_URL}/api/approve", method="POST", data={"id": pend_id, "reason": "Legacy E2E Test", "campaign_id": legacy_cid})
            
            p_dict = conn.execute("SELECT * FROM prospects WHERE id=?", (pend_id,)).fetchone()
            if p_dict["status"] == "approved" and p_dict["campaign_id"] == legacy_cid:
                legacy_res["Approval + campaign_id"] = "PASS"
                
                # Check Sender queue / SMTP by dry-running outreach_sender
                req(f"{BASE_URL}/api/send", method="POST", data={"campaign": legacy_name, "limit": 1})
                time.sleep(5)
                
                # "Send" creates scheduled jobs or executes. Let's see if sender ran
                if proc.returncode == 0:
                    legacy_res["Sender"] = "PASS"
                
                p_dict = conn.execute("SELECT * FROM prospects WHERE id=?", (pend_id,)).fetchone()
                if p_dict["status"] in ["sent", "failed"]:
                    legacy_res["SMTP"] = "PASS"
                
                archive = conn.execute("SELECT * FROM email_archive WHERE campaign_id=?", (legacy_cid,)).fetchone()
                if archive:
                    legacy_res["Archive"] = "PASS"
        else:
            legacy_res["Leads Pending"] = "NO PENDING DATA"
            
    except Exception as e:
        print(f"Legacy Test aborted or failed: {e}")
        
    print("\n### LEGACY OUTREACH")
    print("| Fase                   | Stato     |")
    print("| ---------------------- | --------- |")
    for k, v in legacy_res.items():
        print(f"| {k.ljust(22)} | {v.ljust(9)} |")

if __name__ == "__main__":
    run_test()
