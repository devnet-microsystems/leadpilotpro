import sqlite3
import re
from playwright.sync_api import sync_playwright
from osint_engine.quality import LeadScorer

def main():
    conn = sqlite3.connect('outreach_queue.sqlite3')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT business_email, target_url, confidence_type
        FROM prospects
        LIMIT 20
    """)
    rows = cursor.fetchall()
    
    print("="*100)
    print(f"{'EMAIL':<35} | {'SCORE':<5} | {'TYPE':<22} | {'URL'}")
    print("="*100)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        for email, url, conf_type in rows:
            page_title = ""
            context_text = ""
            
            try:
                response = page.goto(url, timeout=5000, wait_until="domcontentloaded")
                if response and response.status < 400:
                    page_title = page.title()
                    context_text = page.evaluate("document.body ? document.body.innerText.substring(0, 5000) : ''")
            except Exception as e:
                pass
                
            total_score, breakdown = LeadScorer.calculate_score(
                email=email,
                confidence_type=conf_type,
                page_title=page_title,
                context_text=context_text,
                role="CTO",
                industry="SaaS",
                location="Zurich"
            )
            
            print(f"{email:<35} | {total_score:<5} | {conf_type:<22} | {url}")
            # print(f"  Breakdown: {breakdown}")
            
        browser.close()
        
if __name__ == "__main__":
    main()
