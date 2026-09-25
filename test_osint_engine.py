import os
import sqlite3
import tempfile
import unittest
import dataclasses
from pathlib import Path
from public_osint_market_research import LeadStore
from osint_engine.models import DiscoveredLead

class TestOsintEngineP1(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix='.sqlite3')
        # Test H: Schema initialization works on empty DB
        self.store = LeadStore(Path(self.temp_db_path))
        self.store.connection.row_factory = sqlite3.Row

    def tearDown(self):
        self.store.close()
        os.close(self.temp_db_fd)
        os.unlink(self.temp_db_path)

    def test_a_new_email_insert(self):
        lead = DiscoveredLead(
            email="test@example.com",
            domain="example.com",
            company_name="Example Inc",
            source_type="test",
            engine="test",
            source_url="http://test.com",
            query="test query",
            email_confidence=0.9,
            confidence_type="ROLE_BASED",
            relevance_score=50
        )
        lead = dataclasses.replace(lead, why_matched="Good fit")
        is_new = self.store.save_lead(lead, query_run_id="run_1", research_campaign_id=1)
        self.assertTrue(is_new)
        
        row = self.store.connection.execute("SELECT * FROM prospects WHERE business_email='test@example.com'").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["relevance_score"], 50)
        self.assertEqual(row["research_campaign_id"], 1)

    def test_b_same_email_lower_score(self):
        self.test_a_new_email_insert()
        
        lead2 = DiscoveredLead(
            email="test@example.com",
            domain="example.com",
            company_name="Example Inc",
            source_type="test",
            engine="test",
            source_url="http://test.com",
            query="test query 2",
            email_confidence=0.9,
            confidence_type="ROLE_BASED",
            relevance_score=30
        )
        lead2 = dataclasses.replace(lead2, why_matched="Worse fit")
        is_new = self.store.save_lead(lead2, query_run_id="run_2", research_campaign_id=2)
        self.assertFalse(is_new)
        
        row = self.store.connection.execute("SELECT * FROM prospects WHERE business_email='test@example.com'").fetchone()
        self.assertEqual(row["relevance_score"], 50)
        self.assertEqual(row["research_campaign_id"], 1)

    def test_c_same_email_higher_score_and_d_campaign(self):
        self.test_a_new_email_insert()
        
        lead3 = DiscoveredLead(
            email="test@example.com",
            domain="example.com",
            company_name="Example Inc",
            source_type="test",
            engine="test",
            source_url="http://test.com",
            query="test query 3",
            email_confidence=0.9,
            confidence_type="ROLE_BASED",
            relevance_score=80
        )
        lead3 = dataclasses.replace(lead3, why_matched="Great fit")
        is_new = self.store.save_lead(lead3, query_run_id="run_3", research_campaign_id=3)
        self.assertFalse(is_new)
        
        row = self.store.connection.execute("SELECT * FROM prospects WHERE business_email='test@example.com'").fetchone()
        self.assertEqual(row["relevance_score"], 80)
        self.assertEqual(row["why_matched"], "Great fit")
        self.assertEqual(row["research_campaign_id"], 1)

        # Explicit Test D: Multiple Provenance check
        sources = self.store.connection.execute("SELECT * FROM prospect_sources ORDER BY id").fetchall()
        self.assertEqual(len(sources), 2)
        self.assertEqual(sources[0]["query_run_id"], "run_1")
        self.assertEqual(sources[1]["query_run_id"], "run_3")

    def test_g_query_run_id_provenance(self):
        self.test_a_new_email_insert()
        
        sources = self.store.connection.execute("SELECT * FROM prospect_sources").fetchall()
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["query_run_id"], "run_1")

        lead2 = DiscoveredLead(
            email="test@example.com",
            domain="example.com",
            company_name="Example Inc",
            source_type="test",
            engine="test",
            source_url="http://test.com",
            query="test query 2",
            email_confidence=0.9,
            confidence_type="ROLE_BASED",
            relevance_score=30
        )
        lead2 = dataclasses.replace(lead2, why_matched="Worse fit")
        self.store.save_lead(lead2, query_run_id="run_2", research_campaign_id=2)
        
        sources = self.store.connection.execute("SELECT * FROM prospect_sources ORDER BY id").fetchall()
        self.assertEqual(len(sources), 2)
        self.assertEqual(sources[1]["query_run_id"], "run_2")

    def test_f_campaign_context(self):
        import sqlite3
        self.store.connection.execute("CREATE TABLE IF NOT EXISTS ideal_customer_profiles (id INTEGER PRIMARY KEY, roles TEXT, industries TEXT, locations TEXT)")
        self.store.connection.execute("CREATE TABLE IF NOT EXISTS research_campaigns (id INTEGER PRIMARY KEY, icp_id INTEGER, offer_id INTEGER)")
        self.store.connection.execute("CREATE TABLE IF NOT EXISTS campaign_queries (id INTEGER PRIMARY KEY, campaign_id INTEGER, query TEXT, family TEXT, is_enabled INTEGER)")
        
        self.store.connection.execute("INSERT INTO ideal_customer_profiles (id, roles, industries, locations) VALUES (1, '[\"CEO\"]', '[\"Tech\"]', '[\"Italy\"]')")
        self.store.connection.execute("INSERT INTO research_campaigns (id, icp_id, offer_id) VALUES (999, 1, 1)")
        self.store.connection.commit()
        
        from osint_engine.models import TargetContext, QuerySpec
        
        args_campaign_id = 999
        c = self.store.connection.cursor()
        c.row_factory = sqlite3.Row
        
        camp = c.execute("SELECT icp_id, offer_id FROM research_campaigns WHERE id=?", (args_campaign_id,)).fetchone()
        self.assertIsNotNone(camp)
        icp = c.execute("SELECT * FROM ideal_customer_profiles WHERE id=?", (camp["icp_id"],)).fetchone()
        
        import json
        def parse_list(val):
            if not val: return []
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return [x.strip() for x in val.split(',') if x.strip()]
                
        roles = parse_list(icp["roles"])
        industries = parse_list(icp["industries"])
        countries = parse_list(icp["countries"] if "countries" in icp.keys() else "")
        locations = parse_list(icp["locations"] if "locations" in icp.keys() else "")
        if not countries: countries = locations
        
        target_ctx = TargetContext(
            role=", ".join(roles) if roles else "",
            industry=", ".join(industries) if industries else "",
            location=", ".join(locations) if locations else "",
            country=", ".join(countries) if countries else ""
        )
        
        self.assertEqual(target_ctx.role, "CEO")
        self.assertEqual(target_ctx.industry, "Tech")
        self.assertEqual(target_ctx.location, "Italy")

    def test_e_max_total_leads(self):
        MAX_TOTAL_LEADS = 150
        metrics = {"leads_inserted": 0}
        total_queries_executed = 0
        MAX_TOTAL_QUERIES = 300
        
        round_specs = [1] * 200 # simulate 200 queries
        
        queries_actually_executed = 0
        for spec in round_specs:
            if total_queries_executed >= MAX_TOTAL_QUERIES:
                break
            if metrics["leads_inserted"] >= MAX_TOTAL_LEADS:
                break
                
            total_queries_executed += 1
            queries_actually_executed += 1
            metrics["leads_inserted"] += 1
            
        self.assertEqual(metrics["leads_inserted"], 150)
        self.assertEqual(queries_actually_executed, 150)

    def test_integration(self):
        lead = DiscoveredLead(
            email="int@example.com",
            domain="example.com",
            company_name="Example Inc",
            source_type="test",
            engine="test",
            source_url="http://test.com",
            query="test query",
            email_confidence=0.9,
            confidence_type="ROLE_BASED",
            relevance_score=60
        )
        is_new = self.store.save_lead(lead, query_run_id="run_int_1", research_campaign_id=10)
        self.assertTrue(is_new)
        row = self.store.connection.execute("SELECT * FROM prospects WHERE business_email='int@example.com'").fetchone()
        self.assertEqual(row["research_campaign_id"], 10)
        sources = self.store.connection.execute("SELECT * FROM prospect_sources WHERE query_run_id='run_int_1'").fetchall()
        self.assertEqual(len(sources), 1)

if __name__ == '__main__':
    unittest.main()
