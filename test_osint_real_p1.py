import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import sqlite3
import tempfile
import logging
from pathlib import Path

import public_osint_market_research

class TestRealOsintP1(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix='.sqlite3')
        store = public_osint_market_research.LeadStore(Path(self.temp_db_path))
        
        store.connection.execute("CREATE TABLE IF NOT EXISTS ideal_customer_profiles (id INTEGER PRIMARY KEY, roles TEXT, industries TEXT, locations TEXT)")
        store.connection.execute("CREATE TABLE IF NOT EXISTS research_campaigns (id INTEGER PRIMARY KEY, icp_id INTEGER, offer_id INTEGER)")
        store.connection.execute("CREATE TABLE IF NOT EXISTS campaign_queries (id INTEGER PRIMARY KEY, campaign_id INTEGER, query TEXT, family TEXT, is_enabled INTEGER)")
        
        store.connection.commit()
        store.close()

    def tearDown(self):
        os.close(self.temp_db_fd)
        os.unlink(self.temp_db_path)

    @patch('public_osint_market_research.sync_playwright')
    @patch('osint_engine.providers.SearXNGProvider.search')
    @patch('osint_engine.crawler.CompanyCrawler.crawl')
    @patch('osint_engine.quality.LeadScorer.calculate_score')
    @patch('osint_engine.quality.AIExtractor.generate_why_matched')
    @patch('public_osint_market_research.QueryStrategyEngine')
    def test_e_max_total_leads(self, mock_engine, mock_ai, mock_score, mock_crawl, mock_search, mock_pw):
        from osint_engine.models import ProviderResult, ProviderState, UnifiedSearchResult, DiscoveredLead, QuerySpec
        
        mock_engine_instance = MagicMock()
        mock_engine_instance.generate_all_rounds.return_value = {
            1: [QuerySpec(text=f"q{i}", family="TEST", round=1, provider_name="SearXNGProvider") for i in range(100)]
        }
        mock_engine.return_value = mock_engine_instance

        call_counter = [0]
        def search_side_effect(*args, **kwargs):
            call_counter[0] += 1
            idx = call_counter[0]
            return ProviderResult(
                status=ProviderState.SUCCESS,
                results=[UnifiedSearchResult(
                    title=f"Test {idx}", url=f"http://test{idx}.com", domain=f"test{idx}.com", 
                    snippet="test", engine="searxng", query="test query"
                )]
            )
        mock_search.side_effect = search_side_effect
        
        crawl_counter = [0]
        def crawl_side_effect(*args, **kwargs):
            crawl_counter[0] += 1
            call_idx = crawl_counter[0]
            return [
                DiscoveredLead(
                    email=f"test{i}_call{call_idx}@test.com",
                    domain="test.com",
                    source_url="http://test.com",
                    source_type="crawler",
                    engine="crawler",
                    confidence_type="ROLE_BASED",
                    email_confidence=0.9,
                    query="test"
                ) for i in range(20)
            ]
        mock_crawl.side_effect = crawl_side_effect
        mock_score.return_value = (80, {})
        mock_ai.return_value = "AI Reason"
        
        test_args = ["script", "--database", self.temp_db_path, "--role", "CEO", "--max-queries", "30"]
        with patch.object(sys, 'argv', test_args):
            try:
                public_osint_market_research.main()
            except SystemExit:
                pass
            
        conn = sqlite3.connect(self.temp_db_path)
        count = conn.execute("SELECT count(*) FROM prospects").fetchone()[0]
        self.assertGreaterEqual(count, 150, "Should reach MAX_TOTAL_LEADS (150)")
        self.assertLessEqual(count, 170, "Should stop after reaching MAX_TOTAL_LEADS without overshooting more than one batch")
        
        queries_run = conn.execute("SELECT count(*) FROM query_runs").fetchone()[0]
        self.assertLess(queries_run, 30, "Should have stopped before 30 queries because lead budget hit")
        conn.close()

    @patch('public_osint_market_research.QueryStrategyEngine')
    def test_f_campaign_context(self, mock_engine):
        conn = sqlite3.connect(self.temp_db_path)
        conn.execute("INSERT INTO ideal_customer_profiles (id, roles, industries, locations) VALUES (1, '[\"CTO\"]', '[\"Fintech\"]', '[\"Spain\"]')")
        conn.execute("INSERT INTO research_campaigns (id, icp_id, offer_id) VALUES (999, 1, 1)")
        conn.commit()
        conn.close()

        mock_engine_instance = MagicMock()
        mock_engine_instance.generate_all_rounds.return_value = {}
        mock_engine.return_value = mock_engine_instance

        test_args = ["script", "--database", self.temp_db_path, "--campaign-id", "999"]
        with patch.object(sys, 'argv', test_args):
            try:
                public_osint_market_research.main()
            except SystemExit:
                pass

        mock_engine.assert_called_once()
        kwargs = mock_engine.call_args.kwargs
        target_ctx = kwargs['target_ctx']
        
        self.assertEqual(target_ctx.role, "CTO")
        self.assertEqual(target_ctx.industry, "Fintech")
        self.assertEqual(target_ctx.location, "Spain")

    @patch('public_osint_market_research.sync_playwright')
    @patch('osint_engine.providers.SearXNGProvider.search')
    @patch('osint_engine.crawler.CompanyCrawler.crawl')
    @patch('osint_engine.quality.LeadScorer.calculate_score')
    @patch('osint_engine.quality.AIExtractor.generate_why_matched')
    def test_integration_and_provenance(self, mock_ai, mock_score, mock_crawl, mock_search, mock_pw):
        from osint_engine.models import ProviderResult, ProviderState, UnifiedSearchResult, DiscoveredLead
        
        conn = sqlite3.connect(self.temp_db_path)
        conn.execute("INSERT INTO ideal_customer_profiles (id, roles, industries, locations) VALUES (1, '[\"CTO\"]', '[\"Fintech\"]', '[\"Spain\"]')")
        conn.execute("INSERT INTO research_campaigns (id, icp_id, offer_id) VALUES (10, 1, 1)")
        conn.execute("INSERT INTO research_campaigns (id, icp_id, offer_id) VALUES (20, 1, 2)")
        
        conn.execute("INSERT INTO campaign_queries (campaign_id, query, family, is_enabled) VALUES (10, 'query1', 'TEST', 1)")
        conn.execute("INSERT INTO campaign_queries (campaign_id, query, family, is_enabled) VALUES (20, 'query2', 'TEST', 1)")
        conn.commit()
        conn.close()

        mock_search.return_value = ProviderResult(
            status=ProviderState.SUCCESS,
            results=[UnifiedSearchResult(
                title="Test", url="http://test.com", domain="test.com", 
                snippet="test", engine="searxng", query="test query"
            )]
        )
        
        mock_crawl.return_value = [
            DiscoveredLead(
                email="target@example.com",
                domain="example.com",
                source_url="http://example.com",
                source_type="crawler",
                engine="crawler",
                confidence_type="ROLE_BASED",
                email_confidence=0.9,
                query="test"
            )
        ]
        
        mock_ai.return_value = "AI Match"

        mock_score.return_value = (50, {})
        test_args_1 = ["script", "--database", self.temp_db_path, "--campaign-id", "10", "--max-queries", "1"]
        with patch.object(sys, 'argv', test_args_1):
            try:
                public_osint_market_research.main()
            except SystemExit:
                pass
            
        mock_score.return_value = (90, {})
        test_args_2 = ["script", "--database", self.temp_db_path, "--campaign-id", "20", "--max-queries", "1"]
        with patch.object(sys, 'argv', test_args_2):
            try:
                public_osint_market_research.main()
            except SystemExit:
                pass
            
        conn = sqlite3.connect(self.temp_db_path)
        conn.row_factory = sqlite3.Row
        prospects = conn.execute("SELECT * FROM prospects").fetchall()
        print([dict(p) for p in prospects])
        prospects = [p for p in prospects if p["business_email"] == "target@example.com"]
        self.assertEqual(len(prospects), 1, "Should only have one prospect record")
        p = prospects[0]
        self.assertEqual(p["relevance_score"], 90, "Score should have been upgraded")
        self.assertEqual(p["research_campaign_id"], 10, "Original campaign ID should be PRESERVED")
        
        sources = conn.execute("SELECT * FROM prospect_sources WHERE prospect_id=? ORDER BY id", (p["id"],)).fetchall()
        self.assertEqual(len(sources), 2, "Should have exactly two provenance records")
        
        runs = conn.execute("SELECT * FROM query_runs ORDER BY id").fetchall()
        self.assertEqual(len(runs), 2, "Should have 2 query runs")
        
        self.assertEqual(sources[0]["query_run_id"], runs[0]["run_id"])
        self.assertEqual(sources[1]["query_run_id"], runs[1]["run_id"])
        
        conn.close()

if __name__ == '__main__':
    logging.getLogger().setLevel(logging.CRITICAL)
    unittest.main()
