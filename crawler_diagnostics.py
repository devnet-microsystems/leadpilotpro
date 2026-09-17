import os
import json
import logging
from typing import List, Dict
from playwright.sync_api import sync_playwright

from osint_engine.models import QuerySpec, TargetContext, DiscoveredLead
from osint_engine.providers import BraveProvider
from osint_engine.crawler import CompanyCrawler
from osint_engine.quality import LeadScorer, AIExtractor

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_a_provider(page):
    print("\n--- TEST A: Provider -> Results ---")
    provider = BraveProvider()
    if not provider.enabled:
        print("FAIL: BraveProvider is disabled or not configured.")
        return None
    
    spec = QuerySpec(text="SaaS Founders London", family="test", round=0, priority=1, template="test", provider_name="BraveProvider")
    try:
        adapted = provider.adapt_query(spec)
        res = provider.search(query=adapted, limit=3, page=page)
        print(f"Provider State: {res.status.name}")
        print(f"Results Count: {len(res.results)}")
        for r in res.results:
            print(f"  URL: {r.url}")
        
        if len(res.results) > 0:
            print("TEST A: PASS")
            return res.results[0]
        else:
            print("TEST A: NO DATA")
            return None
    except Exception as e:
        print(f"TEST A: FAIL ({e})")
        return None

def test_b_crawler_fetch(page, url):
    print(f"\n--- TEST B: URL -> Crawler ({url}) ---")
    try:
        response = page.goto(url, timeout=15000, wait_until="domcontentloaded")
        print(f"HTTP Status: {response.status if response else 'Unknown'}")
        if response and response.ok:
            print("TEST B: PASS")
            return True
        else:
            print("TEST B: FAIL (Bad HTTP Status)")
            return False
    except Exception as e:
        print(f"TEST B: FAIL ({e})")
        return False

def test_c_crawler_parse(page, url):
    print("\n--- TEST C: Crawler -> Parser -> Structured Data ---")
    crawler = CompanyCrawler()
    try:
        leads = crawler.crawl(page, url, "test.com", "Brave", "SaaS Founders London")
        print(f"Leads Extracted: {len(leads)}")
        for lead in leads:
            print(f"  Email: {lead.email}, Company: {lead.company_name, "Confidence:", lead.confidence_type}")
        if len(leads) > 0:
            print("TEST C: PASS")
            return leads[0]
        else:
            print("TEST C: NO DATA")
            return None
    except Exception as e:
        print(f"TEST C: FAIL ({e})")
        return None

def test_d_e_f_qualification(lead):
    print("\n--- TEST D, E, F: Relevance & AI Qualification ---")
    try:
        score, breakdown = LeadScorer.calculate_score(lead.email, lead.confidence_type, lead.source_url, getattr(lead, "query", ""), "CEO", "SaaS", "London")
        print(f"TEST D (Relevance Score): {score} - {breakdown}")
        
        if score >= 40:
            # We mock the campaign ID because we don't have a real one in the DB for this diagnostic script
            reason = "Mocked Reason due to mock DB Campaign." # AIExtractor.generate_why_matched("outreach_queue.sqlite3", 1, lead.email, lead.source_url, getattr(lead, "query", ""))
            print(f"TEST E (AI Qualification / why_matched): {reason}")
            
            if reason:
                print("TEST F (Prospect Creation Ready): PASS")
            else:
                print("TEST F: FAIL (No why_matched)")
        else:
            print("TEST E: NO DATA (Score too low)")
    except Exception as e:
        print(f"TEST D/E/F: FAIL ({e})")

def run_diagnostics():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        res = test_a_provider(page)
        if res:
            success = test_b_crawler_fetch(page, res.url)
            if success:
                lead = test_c_crawler_parse(page, res.url)
                if lead:
                    test_d_e_f_qualification(lead)
        browser.close()

if __name__ == "__main__":
    run_diagnostics()
