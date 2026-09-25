import unittest
import requests
import sqlite3
import db_connector
import time
import subprocess
import os
import json
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
DB_PATH = Path("outreach_queue.sqlite3").resolve()

class TestP2E2E(unittest.TestCase):
    def setUp(self):
        # We assume the web server is running on 8000 and using outreach_queue.sqlite3
        self.conn = db_connector.get_connection(DB_PATH, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.session = requests.Session()
        resp = self.session.post(f"{BASE_URL}/api/login", json={"username": "admin", "password": "admin"})
        if resp.status_code != 200:
            print("Warning: Login failed. Endpoints might return 401.")
        
    def tearDown(self):
        self.conn.close()
        
    def test_01_quick_search(self):
        print("Testing Quick Search...")
        c = self.conn.cursor()
        p_count_before = c.execute("SELECT COUNT(*) FROM prospects").fetchone()[0]
        
        try:
            resp = self.session.post(f"{BASE_URL}/api/quick_search", json={"query": "Test Dummy"}, timeout=30)
            data = resp.json()
            self.assertTrue(data.get("success", False))
        except Exception as e:
            print("Quick search error:", e)
            
        p_count_after = c.execute("SELECT COUNT(*) FROM prospects").fetchone()[0]
        self.assertEqual(p_count_before, p_count_after, "Quick search should not create prospects in DB")
        print("PASS: Quick Search (No DB Pollution)")

    def test_02_campaign_wizard(self):
        print("Testing Campaign Wizard...")
        test_id = str(time.time())
        resp = self.session.post(f"{BASE_URL}/api/sales_offers", json={"name": f"Test Offer P2 {test_id}", "description": "Desc"})
        resp = self.session.post(f"{BASE_URL}/api/icps", json={"name": f"Test ICP P2 {test_id}", "roles": "CTO", "industries": "Software", "locations": "Milan"})
        
        c = self.conn.cursor()
        offer_id = c.execute("SELECT id FROM sales_offers ORDER BY id DESC LIMIT 1").fetchone()[0]
        icp_id = c.execute("SELECT id FROM ideal_customer_profiles ORDER BY id DESC LIMIT 1").fetchone()[0]
        
        resp = self.session.post(f"{BASE_URL}/api/research_campaigns", json={"name": f"P2 Test Campaign {test_id}", "offer_id": offer_id, "icp_id": icp_id})
        camp_data = resp.json()
        camp_id = camp_data.get("id")
        self.assertIsNotNone(camp_id)
        
        resp = self.session.post(f"{BASE_URL}/api/campaigns/{camp_id}/generate_plan")
        queries = c.execute("SELECT * FROM campaign_queries WHERE campaign_id=?", (camp_id,)).fetchall()
        self.assertTrue(len(queries) > 0, "Queries should be generated")
        print("PASS: Campaign Wizard")
        
        self.__class__.camp_id = camp_id

    def test_03_query_studio(self):
        print("Testing Query Studio...")
        camp_id = getattr(self, "camp_id", None)
        resp = self.session.get(f"{BASE_URL}/api/campaigns/{camp_id}/queries")
        queries = resp.json()
        self.assertTrue(len(queries) > 0)
        
        q_id = queries[0]["id"]
        self.session.post(f"{BASE_URL}/api/campaign_queries/{q_id}/toggle", json={"is_enabled": 0})
        
        c = self.conn.cursor()
        is_enabled = c.execute("SELECT is_enabled FROM campaign_queries WHERE id=?", (q_id,)).fetchone()[0]
        self.assertEqual(is_enabled, 0)
        print("PASS: Query Studio")

    def test_04_launch(self):
        print("Testing Launch...")
        camp_id = getattr(self, "camp_id", None)
        resp = self.session.post(f"{BASE_URL}/api/campaigns/{camp_id}/launch", json={"max_leads": 5})
        self.assertEqual(resp.status_code, 200)
        
        c = self.conn.cursor()
        status = c.execute("SELECT status FROM research_campaigns WHERE id=?", (camp_id,)).fetchone()[0]
        self.assertEqual(status, "RUNNING")
        print("PASS: Launch")

    def test_05_qualified_leads(self):
        resp = self.session.get(f"{BASE_URL}/api/prospects?status=pending_review")
        self.assertEqual(resp.status_code, 200)
        print("PASS: Qualified Leads Endpoint")
        
    def test_06_research_to_outreach(self):
        c = self.conn.cursor()
        now = __import__('datetime').datetime.utcnow().isoformat()
        test_id = str(time.time())
        c.execute("INSERT INTO research_campaigns (name, status, created_at_utc) VALUES (?, 'DRAFT', ?)", (f'Test Campaign {test_id}', now))
        rc_id = c.lastrowid
        c.execute("INSERT INTO prospects (company_name, business_email, status, research_campaign_id, target_url, source_file, imported_at_utc) VALUES ('Dummy Co', ?, 'pending_review', ?, 'http://dummy.com', 'test', ?)", (f'dummy_{test_id}@dummy.com', rc_id, now))
        p_id = c.lastrowid
        self.conn.commit()
        
        self.session.post(f"{BASE_URL}/api/campaigns", json={"name": f"Outreach Target P2 {test_id}", "template": "Test"})
        o_camp_id = c.execute("SELECT id FROM campaigns ORDER BY id DESC LIMIT 1").fetchone()[0]
        
        resp = self.session.post(f"{BASE_URL}/api/approve_selected", json={"ids": [p_id], "campaign_id": o_camp_id, "reason": "Test"})
        
        p = c.execute("SELECT p.status, c.name as campaign, rc.name as research_campaign_name FROM prospects p LEFT JOIN research_campaigns rc ON p.research_campaign_id = rc.id LEFT JOIN campaigns c ON p.campaign_id = c.id WHERE p.id=?", (p_id,)).fetchone()
        self.assertEqual(p["status"], "approved")
        self.assertEqual(p["campaign"], f"Outreach Target P2 {test_id}")
        self.assertEqual(p["research_campaign_name"], f"Test Campaign {test_id}")
        print("PASS: Research -> Outreach")
        
    def test_07_budget(self):
        print("Testing Budget...")
        c = self.conn.cursor()
        now = __import__('datetime').datetime.utcnow().isoformat()
        test_id = str(time.time())
        c.execute("INSERT INTO research_campaigns (name, status, created_at_utc) VALUES (?, 'DRAFT', ?)", (f'Budget Test {test_id}', now))
        c_id = c.lastrowid
        c.execute("INSERT INTO campaign_queries (campaign_id, query, family, is_enabled) VALUES (?, 'Test budget', 'TEST', 1)", (c_id,))
        self.conn.commit()
        
        result = subprocess.run(["python3", "public_osint_market_research.py", "--campaign-id", str(c_id), "--max-leads", "5", "--quick-search"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        print("PASS: Budget")

    def test_08_evidence_feedback(self):
        print("Testing Evidence & Feedback...")
        c = self.conn.cursor()
        now = __import__('datetime').datetime.utcnow().isoformat()
        test_id = str(time.time())
        c.execute("INSERT INTO research_campaigns (name, status, created_at_utc) VALUES (?, 'DRAFT', ?)", (f'Evidence Test {test_id}', now))
        rc_id = c.lastrowid
        c.execute("INSERT INTO prospects (company_name, business_email, status, research_campaign_id, target_url, source_file, imported_at_utc, why_matched) VALUES ('Evidence Co', ?, 'pending_review', ?, 'http://evidence.com', 'test', ?, 'Matches ICP')", (f'evidence_{test_id}@evidence.com', rc_id, now))
        p_id = c.lastrowid
        
        c.execute("INSERT INTO prospect_sources (prospect_id, source_type, engine, source_url, query, discovered_at, query_run_id) VALUES (?, 'html', 'duckduckgo', 'http://evidence.com/team', 'query1', ?, 'run1')", (p_id, now))
        self.conn.commit()
        
        # Test Evidence GET
        resp = self.session.get(f"{BASE_URL}/api/prospects/{p_id}/evidence")
        self.assertEqual(resp.status_code, 200)
        ev_data = resp.json()
        self.assertEqual(ev_data["why_matched"], "Matches ICP")
        self.assertEqual(len(ev_data["sources"]), 1)
        self.assertEqual(ev_data["sources"][0]["query_run_id"], "run1")
        
        # Test Feedback Loop (Reject with Reason)
        resp = self.session.post(f"{BASE_URL}/api/reject_selected", json={"ids": [p_id], "reason": "wrong_role"})
        self.assertEqual(resp.status_code, 200)
        
        p = c.execute("SELECT status, rejection_reason FROM prospects WHERE id=?", (p_id,)).fetchone()
        self.assertEqual(p["status"], "rejected")
        self.assertEqual(p["rejection_reason"], "wrong_role")
        
        print("PASS: Evidence & Feedback")

    def test_09_account_penetration(self):
        print("Testing Account Penetration...")
        from osint_engine.models import DiscoveredLead
        from public_osint_market_research import LeadStore
        
        store = LeadStore("outreach_queue.sqlite3")
        store.connection.row_factory = sqlite3.Row
        c = store.connection.cursor()
        now = __import__('datetime').datetime.utcnow().isoformat()
        test_id = str(time.time())
        c.execute("INSERT INTO research_campaigns (name, status, created_at_utc) VALUES (?, 'DRAFT', ?)", (f'Dedup Test {test_id}', now))
        rc_id = c.lastrowid
        store.connection.commit()
        
        # Insert 3 qualified leads for same domain
        for i in range(3):
            lead = DiscoveredLead(
                domain="dedup.com",
                email=f"user{i}_{test_id}@dedup.com",
                source_type="html",
                engine="test",
                query="test",
                source_url="http://dedup.com",
                company_name="Dedup Co",
                email_confidence=0.99,
                confidence_type="PERSONAL",
                relevance_score=80,
                why_matched="Test"
            )
            store.save_lead(lead, query_run_id="run", campaign_id=rc_id)
            
        # The 4th should be suppressed
        lead = DiscoveredLead(
            domain="dedup.com",
            email=f"user4_{test_id}@dedup.com",
            source_type="html",
            engine="test",
            query="test",
            source_url="http://dedup.com",
            company_name="Dedup Co",
            email_confidence=0.99,
            confidence_type="PERSONAL",
            relevance_score=80,
            why_matched="Test"
        )
        store.save_lead(lead, query_run_id="run", campaign_id=rc_id)
        
        p4 = c.execute("SELECT qualification_status, rejection_reason FROM prospects WHERE business_email=?", (f"user4_{test_id}@dedup.com",)).fetchone()
        self.assertEqual(p4["qualification_status"], "SUPPRESSED")
        self.assertEqual(p4["rejection_reason"], "quota_exceeded")
        print("PASS: Account Penetration Limit")

    def test_10_qualification_gate(self):
        print("Testing Qualification Gate...")
        from osint_engine.models import DiscoveredLead
        from public_osint_market_research import LeadStore
        
        store = LeadStore("outreach_queue.sqlite3")
        store.connection.row_factory = sqlite3.Row
        c = store.connection.cursor()
        now = __import__('datetime').datetime.utcnow().isoformat()
        test_id = str(time.time())
        c.execute("INSERT INTO research_campaigns (name, status, created_at_utc) VALUES (?, 'DRAFT', ?)", (f'Gate Test {test_id}', now))
        rc_id = c.lastrowid
        store.connection.commit()
        
        # 1. Low Score -> UNQUALIFIED
        lead = DiscoveredLead(domain="gate.com", email=f"1_{test_id}@gate.com", source_type="html", engine="test", query="test", source_url="http://gate.com", company_name="Gate Co", email_confidence=0.99, confidence_type="PERSONAL", relevance_score=30, why_matched="Test")
        store.save_lead(lead, query_run_id="run", campaign_id=rc_id)
        p1 = c.execute("SELECT qualification_status, status FROM prospects WHERE business_email=?", (f"1_{test_id}@gate.com",)).fetchone()
        self.assertEqual(p1["qualification_status"], "UNQUALIFIED")
        self.assertEqual(p1["status"], "rejected")
        
        # 2. SYSTEM Email -> UNQUALIFIED
        lead = DiscoveredLead(domain="gate.com", email=f"2_{test_id}@gate.com", source_type="html", engine="test", query="test", source_url="http://gate.com", company_name="Gate Co", email_confidence=0.99, confidence_type="SYSTEM", relevance_score=80, why_matched="Test")
        store.save_lead(lead, query_run_id="run", campaign_id=rc_id)
        p2 = c.execute("SELECT qualification_status, status FROM prospects WHERE business_email=?", (f"2_{test_id}@gate.com",)).fetchone()
        self.assertEqual(p2["qualification_status"], "UNQUALIFIED")
        self.assertEqual(p2["status"], "rejected")
        
        # 3. High Score, Good Email -> QUALIFIED
        lead = DiscoveredLead(domain="gate.com", email=f"3_{test_id}@gate.com", source_type="html", engine="test", query="test", source_url="http://gate.com", company_name="Gate Co", email_confidence=0.95, confidence_type="PERSONAL", relevance_score=85, why_matched="Test")
        store.save_lead(lead, query_run_id="run", campaign_id=rc_id)
        p3 = c.execute("SELECT qualification_status, status FROM prospects WHERE business_email=?", (f"3_{test_id}@gate.com",)).fetchone()
        self.assertEqual(p3["qualification_status"], "QUALIFIED")
        self.assertEqual(p3["status"], "pending_review")
        
        print("PASS: Qualification Gate")

if __name__ == "__main__":
    unittest.main()
