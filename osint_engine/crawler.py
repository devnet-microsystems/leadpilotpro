import re
import os
import time
import logging
from typing import List, Set, Dict, Optional
from urllib.parse import urljoin, urlsplit
from datetime import datetime, timezone
from playwright.sync_api import Page, Error as PlaywrightError

from .models import DiscoveredLead
from .normalization import URLNormalizer
from .quality import LeadScorer, AIExtractor

EMAIL_PATTERN = re.compile(r"(?<![\w.+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,63})(?![\w.-])", re.IGNORECASE)
CONTACT_LINK_KEYWORDS = ("contact", "about", "team", "company", "support", "impressum", "legal", "privacy")
PERSONAL_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "hotmail.com", "icloud.com", "live.com",
    "me.com", "msn.com", "outlook.com", "proton.me", "protonmail.com", "yahoo.com",
}

class CompanyCrawler:
    def __init__(self, role: str = "", industry: str = "", location: str = "", campaign_id: int = None, db_path: str = None):
        self.role = role
        self.industry = industry
        self.location = location
        self.campaign_id = campaign_id
        self.db_path = db_path
        self.max_pages_per_domain = int(os.getenv("MAX_PAGES_PER_DOMAIN", "5"))
        self.crawl_timeout_ms = int(os.getenv("CRAWL_TIMEOUT", "8")) * 1000
        self.max_total_pages = int(os.getenv("MAX_TOTAL_CRAWL_PAGES", "500"))
        self.pages_crawled_this_run = 0
        self.domain_page_counts: Dict[str, int] = {}
        self.visited_urls: Set[str] = set()

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    def _evaluate_email(self, email: str) -> tuple[str, float]:
        if email.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico", ".tiff", ".css", ".js", ".mp4", ".mp3", ".pdf", ".zip", ".tar.gz", ".woff", ".woff2", ".ttf")):
            return "INVALID", 0.0
        local_part, _, email_domain = email.lower().partition("@")
        
        if not local_part or not email_domain:
            return "INVALID", 0.0
            
        if email_domain in PERSONAL_EMAIL_DOMAINS:
            return "PERSONAL_EMAIL_PROVIDER", 0.10
            
        if re.match(r"^[0-9a-f]{10,}$", local_part):
            return "SYSTEM", 0.01

        role_based = {
            "info", "contact", "sales", "support", "hello", "office", "admin", "privacy",
            "billing", "marketing", "press", "careers", "jobs", "hr", "team", "agency",
            "legal", "compliance", "abuse", "security", "webmaster", "service", "client",
            "reservation", "help", "media", "enquiries", "inquiries", "noreply", "no-reply"
        }
        
        local_parts = re.split(r'[._-]', local_part)
        if any(part in role_based for part in local_parts):
            return "ROLE_BASED", 0.40
            
        if "." in local_part:
            return "PERSONAL", 0.98
            
        return "PERSONAL", 0.90

    def crawl(self, page: Page, start_url: str, domain: str, engine: str, query: str) -> List[DiscoveredLead]:
        if self.pages_crawled_this_run >= self.max_total_pages:
            logging.warning("MAX_TOTAL_CRAWL_PAGES reached")
            return []
            
        if self.domain_page_counts.get(domain, 0) >= self.max_pages_per_domain:
            return []

        to_visit: List[str] = [start_url]
        leads: List[DiscoveredLead] = []
        
        while to_visit and self.domain_page_counts.get(domain, 0) < self.max_pages_per_domain and self.pages_crawled_this_run < self.max_total_pages:
            current_url = to_visit.pop(0)
            if current_url in self.visited_urls:
                continue
                
            self.visited_urls.add(current_url)
            self.domain_page_counts[domain] = self.domain_page_counts.get(domain, 0) + 1
            self.pages_crawled_this_run += 1
            
            try:
                response = page.goto(current_url, wait_until="domcontentloaded", timeout=self.crawl_timeout_ms)
                if response is None or response.status >= 400:
                    continue
                page.wait_for_timeout(500)
            except PlaywrightError:
                continue

            try:
                html = page.content()
                page_title = page.title()
                # Use body innerText as context (limit to 10000 chars for speed)
                context_text = page.evaluate("document.body ? document.body.innerText.substring(0, 10000) : ''")
            except PlaywrightError:
                continue

            # Extract Emails
            raw_emails = set(match.group(1).strip(".,;:)]}>\"'").lower() for match in EMAIL_PATTERN.finditer(html))
            try:
                mailtos = page.locator('a[href^="mailto:"]').evaluate_all(
                    "els => els.map(el => el.getAttribute('href').replace(/^mailto:/i, ''))"
                )
                for m in mailtos:
                    clean_m = m.split("?", 1)[0].strip().lower()
                    if EMAIL_PATTERN.fullmatch(clean_m):
                        raw_emails.add(clean_m)
            except PlaywrightError:
                pass

            for email in raw_emails:
                conf_type, conf_score = self._evaluate_email(email)
                if conf_type != "INVALID":
                    total_score, _ = LeadScorer.calculate_score(
                        email=email,
                        confidence_type=conf_type,
                        page_title=page_title,
                        context_text=context_text,
                        role=self.role,
                        industry=self.industry,
                        location=self.location
                    )
                    
                    why_matched = ""
                    if self.campaign_id and self.db_path and total_score >= 40:
                        why_matched = AIExtractor.generate_why_matched(
                            db_path=self.db_path,
                            campaign_id=self.campaign_id,
                            lead_email=email,
                            page_title=page_title,
                            context_text=context_text
                        )
                        
                    leads.append(DiscoveredLead(
                        email=email,
                        domain=domain,
                        source_url=current_url,
                        source_type="public_web",
                        engine=engine,
                        confidence_type=conf_type,
                        email_confidence=conf_score,
                        query=query,
                        company_name=domain,
                        relevance_score=total_score,
                        why_matched=why_matched
                    ))

            # Discover Contact Pages (only on first page load)
            if current_url == start_url:
                try:
                    anchors = page.locator("a[href]")
                    for index in range(min(anchors.count(), 250)):
                        anchor = anchors.nth(index)
                        href = anchor.get_attribute("href") or ""
                        label = (anchor.inner_text(timeout=1_500) or "").lower()
                        candidate = URLNormalizer.normalize(urljoin(page.url, href))
                        
                        if candidate and URLNormalizer.extract_domain(candidate) == domain:
                            if any(kw in f"{label} {candidate.lower()}" for kw in CONTACT_LINK_KEYWORDS):
                                if candidate not in self.visited_urls and candidate not in to_visit:
                                    to_visit.append(candidate)
                except PlaywrightError:
                    pass

        return leads
