import os
import json
import base64
import logging
import urllib.parse
from typing import List, Optional
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from playwright.sync_api import Page, Error as PlaywrightError
import urllib.request
import urllib.error
import socket

from .models import UnifiedSearchResult, QuerySpec, ProviderState, ProviderResult
from .normalization import URLNormalizer, DomainClassifier

NEGATIVE_SITES = [
    "linkedin.com", "apollo.io", "lusha.com"
]

def get_db_setting(key: str, default: str) -> str:
    try:
        import sqlite3
        conn = sqlite3.connect("outreach_queue.sqlite3")
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        conn.close()
        if row and row[0] is not None:
            return row[0]
    except Exception:
        pass
    return default

class UnifiedSearchProvider(ABC):
    def __init__(self):
        self.enabled = True
        self.name = self.__class__.__name__

    @abstractmethod
    def search(self, query: str, limit: int, page: Optional[Page] = None, **kwargs) -> ProviderResult:
        pass

    def adapt_query(self, spec: QuerySpec) -> str:
        return spec.text

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

class DuckDuckGoProvider(UnifiedSearchProvider):
    def __init__(self):
        super().__init__()
        db_val = get_db_setting("ddg_enabled", "")
        if db_val:
            self.enabled = db_val.lower() == "true"
        else:
            self.enabled = os.getenv("DDG_ENABLED", "true").lower() == "true"
        
    def adapt_query(self, spec: QuerySpec) -> str:
        q = spec.text
        for site in NEGATIVE_SITES:
            q += f" -site:{site}"
        return q

    def search(self, query: str, limit: int, page: Optional[Page] = None, **kwargs) -> ProviderResult:
        if not page:
            return ProviderResult(ProviderState.ERROR, [], "DuckDuckGoProvider requires a Playwright Page object")
            
        import time
        start_time = time.time()
        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            response = page.goto(url, wait_until="domcontentloaded", timeout=15000)
            
            if response and response.status == 429:
                latency = int((time.time() - start_time) * 1000)
                return ProviderResult(ProviderState.RATE_LIMITED, [], "HTTP 429", 429, latency)
            
            # Extract links via Playwright locator
            locator = page.locator('a.result__snippet')
            count = locator.count()
            
            if count == 0:
                content = page.content()
                latency = int((time.time() - start_time) * 1000)
                if "chrome-error://chromewebdata/" in url or "chrome-error" in content:
                    return ProviderResult(ProviderState.BLOCKED, [], "Browser navigation blocked", None, latency)
                if "CAPTCHA" in content or "robot" in content.lower():
                    return ProviderResult(ProviderState.BLOCKED, [], "CAPTCHA detected", None, latency)
                return ProviderResult(ProviderState.ZERO_RESULTS, [], "No results found", response.status if response else 200, latency)
            
            raw_links = []
            for i in range(count):
                href = locator.nth(i).get_attribute("href")
                if href:
                    if 'uddg=' in href:
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                        if 'uddg' in parsed:
                            href = parsed['uddg'][0]
                    raw_links.append(href)
            
            results = []
            rank = 1
            for href in raw_links:
                if href.startswith('//lite.duckduckgo.com') or href.startswith('/lite/'):
                    continue
                    
                norm_url = URLNormalizer.normalize(href)
                domain = URLNormalizer.extract_domain(norm_url)
                if DomainClassifier.is_allowed(domain):
                    results.append(UnifiedSearchResult(
                        title="DDG Result", 
                        url=norm_url, 
                        domain=domain, 
                        snippet="", 
                        engine="duckduckgo", 
                        query=query, 
                        rank=rank,
                        discovered_at=self._utc_now()
                    ))
                    rank += 1
                    if len(results) >= limit:
                        break
                        
            latency = int((time.time() - start_time) * 1000)
            status = ProviderState.SUCCESS if results else ProviderState.ZERO_RESULTS
            return ProviderResult(status, results, "", response.status if response else 200, latency)
        except PlaywrightError as e:
            latency = int((time.time() - start_time) * 1000)
            logging.error(f"DuckDuckGo Playwright error: {e}")
            return ProviderResult(ProviderState.ERROR, [], str(e), None, latency)
        except Exception as e:
            latency = int((time.time() - start_time) * 1000)
            logging.error(f"DuckDuckGo search error: {e}")
            return ProviderResult(ProviderState.ERROR, [], str(e), None, latency)

class BingProvider(UnifiedSearchProvider):
    def __init__(self):
        super().__init__()
        self.enabled = False # Disabled as per requirements (experimental)

    def search(self, query: str, limit: int, page: Optional[Page] = None, **kwargs) -> ProviderResult:
        if not self.enabled:
            return ProviderResult(ProviderState.OFF, [], "BingProvider is disabled")
        if not page:
            return ProviderResult(ProviderState.ERROR, [], "BingProvider requires a Playwright Page object")
            
        url = f"https://www.bing.com/search?q={urllib.parse.quote_plus(query)}&cc=US&setlang=en"
        
        import time
        start_time = time.time()
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=25000)
            latency = int((time.time() - start_time) * 1000)
            if response is None:
                return ProviderResult(ProviderState.ERROR, [], "No response", None, latency)
            if response.status == 429:
                return ProviderResult(ProviderState.RATE_LIMITED, [], "HTTP 429", 429, latency)
                
            page.wait_for_timeout(2000)
            
            anchors = page.locator("li.b_algo h2 a").evaluate_all("els => els.map(e => e.href)")
            if not anchors:
                content = page.content()
                if "CAPTCHA" in content or "robot" in content.lower():
                    return ProviderResult(ProviderState.BLOCKED, [], "CAPTCHA detected", response.status, latency)
                return ProviderResult(ProviderState.ZERO_RESULTS, [], "No results found", response.status, latency)
            
            results = []
            rank = 1
            for href in anchors:
                if 'bing.com/ck/a' in href:
                    qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                    if 'u' in qs:
                        u_val = qs['u'][0]
                        if u_val.startswith('a1'):
                            u_val = u_val[2:]
                            u_val += '=' * (-len(u_val) % 4)
                            try:
                                href = base64.b64decode(u_val).decode('utf-8', errors='ignore')
                            except Exception:
                                pass
                
                norm_url = URLNormalizer.normalize(href)
                domain = URLNormalizer.extract_domain(norm_url)
                if DomainClassifier.is_allowed(domain):
                    results.append(UnifiedSearchResult(
                        title="Bing Result", 
                        url=norm_url, 
                        domain=domain, 
                        snippet="", 
                        engine="bing", 
                        query=query, 
                        rank=rank,
                        discovered_at=self._utc_now()
                    ))
                    rank += 1
                    if len(results) >= limit:
                        break
            
            status = ProviderState.SUCCESS if results else ProviderState.ZERO_RESULTS
            return ProviderResult(status, results, "", response.status, latency)
        except PlaywrightError as e:
            latency = int((time.time() - start_time) * 1000)
            logging.error(f"Bing Playwright error: {e}")
            return ProviderResult(ProviderState.ERROR, [], str(e), None, latency)
        except Exception as e:
            latency = int((time.time() - start_time) * 1000)
            logging.error(f"Bing search error: {e}")
            return ProviderResult(ProviderState.ERROR, [], str(e), None, latency)

class SearXNGProvider(UnifiedSearchProvider):
    def __init__(self):
        super().__init__()
        self.base_url = get_db_setting("searxng_url", os.getenv("SEARXNG_URL", "http://localhost:8080")).rstrip("/")
        db_val = get_db_setting("searxng_enabled", "")
        if db_val:
            self.enabled = db_val.lower() == "true"
        else:
            self.enabled = os.getenv("SEARXNG_ENABLED", "true").lower() == "true"
        
    def adapt_query(self, spec: QuerySpec) -> str:
        q = spec.text
        for site in NEGATIVE_SITES:
            q += f" -site:{site}"
        return q

    def search(self, query: str, limit: int, page: Optional[Page] = None, **kwargs) -> ProviderResult:
        if not self.enabled:
            return ProviderResult(ProviderState.OFF, [], "SearXNGProvider is disabled")
            
        url = f"{self.base_url}/search?q={urllib.parse.quote_plus(query)}&format=json"
        
        import time
        start_time = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as response:
                latency = int((time.time() - start_time) * 1000)
                if response.status == 429:
                    return ProviderResult(ProviderState.RATE_LIMITED, [], "HTTP 429", 429, latency)
                if response.status >= 500:
                    return ProviderResult(ProviderState.ERROR, [], f"HTTP {response.status}", response.status, latency)
                if response.status != 200:
                    return ProviderResult(ProviderState.ERROR, [], f"HTTP {response.status}", response.status, latency)
                data = json.loads(response.read().decode('utf-8'))
                
            results = []
            rank = 1
            for item in data.get('results', []):
                href = item.get('url', '')
                norm_url = URLNormalizer.normalize(href)
                domain = URLNormalizer.extract_domain(norm_url)
                if DomainClassifier.is_allowed(domain):
                    results.append(UnifiedSearchResult(
                        title=item.get('title', ''), 
                        url=norm_url, 
                        domain=domain, 
                        snippet=item.get('content', ''), 
                        engine="searxng", 
                        query=query, 
                        rank=rank,
                        discovered_at=self._utc_now()
                    ))
                    rank += 1
                    if len(results) >= limit:
                        break
            
            unresponsive = data.get('unresponsive_engines', [])
            if not results:
                if unresponsive:
                    errors = str(unresponsive)
                    if "too many requests" in errors.lower():
                        return ProviderResult(ProviderState.RATE_LIMITED, [], f"Upstream rate limited: {errors}", 200, latency)
                    return ProviderResult(ProviderState.DEGRADED, [], f"Upstream errors: {errors}", 200, latency)
                return ProviderResult(ProviderState.ZERO_RESULTS, [], "No results found", 200, latency)
            
            status = ProviderState.SUCCESS
            return ProviderResult(status, results, "", 200, latency)
            
        except urllib.error.HTTPError as e:
            latency = int((time.time() - start_time) * 1000)
            if e.code == 429:
                return ProviderResult(ProviderState.RATE_LIMITED, [], "HTTP 429", 429, latency)
            if e.code in [403, 401]:
                return ProviderResult(ProviderState.BLOCKED, [], f"HTTP {e.code}", e.code, latency)
            return ProviderResult(ProviderState.ERROR, [], f"HTTP {e.code}: {e.reason}", e.code, latency)
        except Exception as e:
            latency = int((time.time() - start_time) * 1000)
            logging.error(f"SearXNG search error: {e}")
            return ProviderResult(ProviderState.ERROR, [], str(e), None, latency)

class BraveProvider(UnifiedSearchProvider):
    def __init__(self):
        super().__init__()
        self.api_key = get_db_setting("brave_api_key", os.getenv("BRAVE_API_KEY", ""))
        db_val = get_db_setting("brave_enabled", "")
        if db_val:
            self.enabled = db_val.lower() == "true"
        else:
            self.enabled = os.getenv("BRAVE_ENABLED", "true" if self.api_key else "false").lower() == "true"
            
        if self.enabled and not self.api_key:
            logging.warning("BraveProvider is enabled but brave_api_key is missing. Skipping provider.")
            self.enabled = False
            
    def adapt_query(self, spec: QuerySpec) -> str:
        q = spec.text
        for site in NEGATIVE_SITES:
            q += f" -site:{site}"
        return q

    def search(self, query: str, limit: int, page: Optional[Page] = None, **kwargs) -> ProviderResult:
        if not self.enabled:
            return ProviderResult(ProviderState.OFF, [], "BraveProvider is disabled")
            
        # Respect Brave API limit: 600 chars / 75 words max
        words = query.split()
        if len(words) > 75:
            query = " ".join(words[:75])
        if len(query) > 600:
            query = query[:600]
            
        url = f"https://api.search.brave.com/res/v1/web/search?q={urllib.parse.quote_plus(query)}&count={min(limit, 20)}"
        
        country = kwargs.get('country')
        if country:
            # Map standard baseline countries to ISO-3166-1 alpha-2 for Brave API
            c_map = {"italy": "it", "germany": "de", "switzerland": "ch", "uk": "gb", "us": "us"}
            mapped_c = c_map.get(country.lower(), country.lower()[:2]) # fallback to first 2 letters
            url += f"&country={mapped_c}"
            
        search_lang = kwargs.get('search_lang')
        if search_lang:
            url += f"&search_lang={search_lang}"
            
        ui_lang = kwargs.get('ui_lang')
        if ui_lang:
            url += f"&ui_lang={ui_lang}"
        
        import time
        time.sleep(1.2)  # Respect Brave API Free Tier limit (1 req/sec)
        start_time = time.time()
        try:
            req = urllib.request.Request(url, headers={
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key
            })
            with urllib.request.urlopen(req, timeout=15) as response:
                latency = int((time.time() - start_time) * 1000)
                if response.status == 429:
                    return ProviderResult(ProviderState.RATE_LIMITED, [], "HTTP 429", 429, latency)
                if response.status != 200:
                    return ProviderResult(ProviderState.ERROR, [], f"HTTP {response.status}", response.status, latency)
                data = json.loads(response.read().decode('utf-8'))
                
            results = []
            rank = 1
            web_results = data.get('web', {}).get('results', [])
            for item in web_results:
                href = item.get('url', '')
                norm_url = URLNormalizer.normalize(href)
                domain = URLNormalizer.extract_domain(norm_url)
                if DomainClassifier.is_allowed(domain):
                    results.append(UnifiedSearchResult(
                        title=item.get('title', ''), 
                        url=norm_url, 
                        domain=domain, 
                        snippet=item.get('description', ''), 
                        engine="brave", 
                        query=query, 
                        rank=rank,
                        discovered_at=self._utc_now()
                    ))
                    rank += 1
                    if len(results) >= limit:
                        break
            
            status = ProviderState.SUCCESS if results else ProviderState.ZERO_RESULTS
            return ProviderResult(status, results, "", 200, latency)
            
        except urllib.error.HTTPError as e:
            latency = int((time.time() - start_time) * 1000)
            if e.code == 429:
                return ProviderResult(ProviderState.RATE_LIMITED, [], "HTTP 429", 429, latency)
            if e.code in [403, 401]:
                return ProviderResult(ProviderState.BLOCKED, [], f"HTTP {e.code}", e.code, latency)
            if e.code >= 500:
                return ProviderResult(ProviderState.ERROR, [], f"HTTP {e.code}", e.code, latency)
            return ProviderResult(ProviderState.ERROR, [], f"HTTP {e.code}: {e.reason}", e.code, latency)
        except urllib.error.URLError as e:
            latency = int((time.time() - start_time) * 1000)
            if isinstance(e.reason, socket.timeout) or "timeout" in str(e.reason).lower():
                return ProviderResult(ProviderState.DEGRADED, [], "Timeout", None, latency)
            return ProviderResult(ProviderState.ERROR, [], f"Network error: {str(e.reason)}", None, latency)
        except Exception as e:
            latency = int((time.time() - start_time) * 1000)
            logging.error(f"Brave search error: {e}")
            return ProviderResult(ProviderState.ERROR, [], str(e), None, latency)
