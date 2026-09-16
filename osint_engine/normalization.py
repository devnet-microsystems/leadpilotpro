import re
from urllib.parse import urlsplit, urlunsplit

DISALLOWED_HOST_SUFFIXES = {
    "duckduckgo.com", "google.com", "bing.com", "yahoo.com", "linkedin.com",
    "facebook.com", "instagram.com", "x.com", "twitter.com", "youtube.com",
    "tiktok.com", "clutch.co", "designrush.com", "sortlist.com", "themanifest.com",
    "yelp.com", "yellowpages.com", "crunchbase.com", "zoominfo.com", "apollo.io",
    "goodfirms.co", "wikipedia.org", "reddit.com", "amazon.com", "microsoft.com",
    # Data brokers & lead gen
    "hunter.io", "rocketreach.co", "skrapp.io", "aeroleads.com", "contactout.com",
    "anymailfinder.com", "lusha.com", "seamless.ai", "leadiq.com", "upwork.com",
    "fiverr.com", "trustpilot.com", "g2.com", "capterra.com", "glassdoor.com",
    # Tech / Docs / Repos
    "github.com", "stripe.com", "box.com", "sentry.io", "medium.com", "quora.com",
    "zhihu.com", "stackoverflow.com", "atlassian.com", "hubspot.com"
}

class URLNormalizer:
    @staticmethod
    def normalize(url: str) -> str:
        url = url.strip()
        if not url:
            return ""
        if url.startswith("//"):
            url = "https:" + url
        if not url.startswith(("http://", "https://")):
            return ""
        
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ""
            
        # Remove tracking parameters
        query = parsed.query
        if query:
            clean_params = []
            for param in query.split('&'):
                if not param.lower().startswith(('utm_', 'fbclid=', 'gclid=', 'ref=', 'source=')):
                    clean_params.append(param)
            query = '&'.join(clean_params)
            
        # Lowercase hostname and remove trailing slashes from path if empty
        path = parsed.path or "/"
        
        return urlunsplit((parsed.scheme, parsed.netloc.lower(), path, query, ""))

    @staticmethod
    def extract_domain(url: str) -> str:
        parsed = urlsplit(url)
        netloc = parsed.netloc.lower()
        # Remove www.
        if netloc.startswith("www."):
            netloc = netloc[4:]
        # Remove port if present
        netloc = netloc.split(":")[0]
        return netloc

class DomainClassifier:
    @staticmethod
    def is_allowed(domain: str) -> bool:
        if not domain:
            return False
            
        return not any(
            domain == suffix or domain.endswith("." + suffix)
            for suffix in DISALLOWED_HOST_SUFFIXES
        )
