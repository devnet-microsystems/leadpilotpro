"""
product_intelligence/extractor.py

Content Extraction Layer — converts any supported source format
(URL / PDF / plain text) into a normalised ProductSourceContent object.

Security controls applied:
 - URL: http/https only, SSRF-block on private CIDRs, size cap, redirect cap
 - PDF: magic-bytes validation, size cap, source count cap, no execution
 - TEXT: length cap, whitespace normalisation
"""
import hashlib
import io
import ipaddress
import logging
import re
import socket
import textwrap
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import requests

from .models import ProductSourceContent, SourceType

logger = logging.getLogger(__name__)

# ── Security constants ──────────────────────────────────────────────────────
MAX_URL_RESPONSE_BYTES = 5 * 1024 * 1024   # 5 MB
MAX_URL_REDIRECTS      = 3
URL_FETCH_TIMEOUT      = 15                  # seconds

MAX_PDF_BYTES          = 20 * 1024 * 1024  # 20 MB per PDF
MAX_PDF_SOURCES        = 10               # per product
MAX_TEXT_CHARS         = 100_000

# ── Private / loopback CIDRs to block (SSRF) ───────────────────────────────
PRIVATE_CIDRS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

# ── HTML elements to strip before text extraction ───────────────────────────
STRIP_TAGS = {
    "script", "style", "noscript", "header", "footer", "nav",
    "aside", "form", "button", "svg", "img", "link", "meta",
    "iframe", "object", "embed",
}

# Content elements likely carrying substance
CONTENT_TAGS = {
    "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "td", "th", "blockquote", "article", "section", "main",
}


def _sha256(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _is_private_ip(hostname: str) -> bool:
    """Return True if the hostname resolves to a private/loopback address."""
    try:
        addr = ipaddress.ip_address(socket.gethostbyname(hostname))
        return any(addr in net for net in PRIVATE_CIDRS)
    except (socket.gaierror, ValueError):
        return False


def _clean_html(html: str, source_url: str = "") -> str:
    """Strip boilerplate, extract useful text nodes."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove noise tags entirely
    for tag in soup.find_all(STRIP_TAGS):
        tag.decompose()

    # Try to find a main content block first
    main = soup.find("main") or soup.find(id=re.compile(r"content|main|body", re.I))
    root = main if main else soup

    parts = []
    for el in root.find_all(CONTENT_TAGS):
        text = el.get_text(separator=" ", strip=True)
        if len(text) > 20:  # skip trivial snippets
            parts.append(text)

    if not parts:
        # Fallback: whole body text
        parts = [soup.get_text(separator="\n", strip=True)]

    return "\n".join(parts)


def _normalise_text(text: str) -> str:
    """Collapse whitespace runs, strip leading/trailing space per line."""
    lines = [re.sub(r"\s{2,}", " ", line).strip() for line in text.splitlines()]
    # Remove blank-line clusters (keep max 1 blank between paragraphs)
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return cleaned.strip()


# ──────────────────────────────────────────────────────────────────────────────
# Public extraction functions
# ──────────────────────────────────────────────────────────────────────────────

def extract_from_text(raw_text: str, source_name: str = "paste") -> ProductSourceContent:
    """Extract from plain pasted text."""
    if len(raw_text) > MAX_TEXT_CHARS:
        raise ValueError(
            f"Text too large ({len(raw_text):,} chars). Max allowed: {MAX_TEXT_CHARS:,}."
        )

    normalised = _normalise_text(raw_text)
    digest = _sha256(normalised)

    return ProductSourceContent(
        source_type=SourceType.TEXT,
        source_name=source_name,
        source_url=None,
        extracted_text=normalised,
        content_hash=digest,
        word_count=len(normalised.split()),
        char_count=len(normalised),
    )


def _extract_url_with_browser(url: str) -> tuple[str, str]:
    """Fallback browser extraction for JS-heavy / bot-protected pages.

    Every navigation request is checked before it is allowed to leave the
    browser context. Private/loopback destinations are blocked to preserve the
    same SSRF boundary used by the HTTP extractor.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        raise ValueError(f"Browser fallback unavailable: {e}") from e

    def route_handler(route):
        request_url = route.request.url
        parsed = urlparse(request_url)
        if parsed.scheme not in ("http", "https"):
            route.abort()
            return
        hostname = parsed.hostname or ""
        if not hostname or _is_private_ip(hostname):
            route.abort()
            return
        route.continue_()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="LeadPilotPro/5.1 ProductIntelligence (+product-analysis)",
            java_script_enabled=True,
        )
        page = context.new_page()
        page.route("**/*", route_handler)
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=URL_FETCH_TIMEOUT * 1000)
            final_url = page.url
            final_host = urlparse(final_url).hostname or ""
            if not final_host or _is_private_ip(final_host):
                raise ValueError("Browser navigation ended on a private/loopback address.")

            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass

            html = page.content()
            text = _normalise_text(_clean_html(html, source_url=final_url))
            return text, final_url
        finally:
            context.close()
            browser.close()


def extract_from_url(url: str) -> ProductSourceContent:
    """Fetch a public URL and extract its main text content."""
    # ── Validation ──────────────────────────────────────────────────────────
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http/https URLs are accepted.")

    hostname = parsed.hostname or ""
    if not hostname:
        raise ValueError("URL has no valid hostname.")

    if _is_private_ip(hostname):
        raise ValueError(
            "Requests to private/loopback addresses are not permitted (SSRF protection)."
        )

    # ── Fetch ───────────────────────────────────────────────────────────────
    session = requests.Session()
    session.max_redirects = MAX_URL_REDIRECTS
    browser_fallback_reason = None
    try:
        resp = session.get(
            url,
            timeout=URL_FETCH_TIMEOUT,
            headers={"User-Agent": "LeadPilotPro/5.1 ProductIntelligence (+product-analysis)"},
            stream=True,
        )
        resp.raise_for_status()

        # Read with size cap
        chunks = []
        size = 0
        for chunk in resp.iter_content(chunk_size=64 * 1024):
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_URL_RESPONSE_BYTES:
                logger.warning("URL response truncated at %d bytes: %s", size, url)
                break

        raw_bytes = b"".join(chunks)
        encoding = resp.encoding or "utf-8"
        html = raw_bytes.decode(encoding, errors="replace")
    except requests.RequestException as e:
        browser_fallback_reason = f"HTTP fetch failed: {e}"
        html = None
        resp = None

    # ── Extract ─────────────────────────────────────────────────────────────
    if html is not None:
        normalised = _normalise_text(_clean_html(html, source_url=url))
        canonical_url = resp.url
        # A tiny HTML shell is often a JS challenge / empty SPA. Give the
        # browser fallback a chance before treating it as a valid source.
        if len(normalised) < 120:
            browser_fallback_reason = f"HTTP extraction returned too little text ({len(normalised)} chars)."

    if browser_fallback_reason:
        logger.info("URL browser fallback for %s: %s", url, browser_fallback_reason)
        normalised, canonical_url = _extract_url_with_browser(url)

    digest = _sha256(normalised)
    if len(normalised) < 20:
        raise ValueError("Could not extract meaningful text from URL. Try the page URL directly or upload a PDF/text source.")

    return ProductSourceContent(
        source_type=SourceType.URL,
        source_name=parsed.netloc or url[:80],
        source_url=canonical_url,
        extracted_text=normalised,
        content_hash=digest,
        word_count=len(normalised.split()),
        char_count=len(normalised),
        metadata={"status_code": resp.status_code, "content_type": resp.headers.get("content-type", "")},
    )


def extract_from_pdf(file_bytes: bytes, filename: str = "document.pdf") -> ProductSourceContent:
    """Extract text from a PDF binary, page by page."""
    # ── Size guard ───────────────────────────────────────────────────────────
    if len(file_bytes) > MAX_PDF_BYTES:
        raise ValueError(
            f"PDF too large ({len(file_bytes) / (1024*1024):.1f} MB). Max: {MAX_PDF_BYTES // (1024*1024)} MB."
        )

    # ── Magic bytes check ────────────────────────────────────────────────────
    if not file_bytes.startswith(b"%PDF"):
        raise ValueError("File does not appear to be a valid PDF (bad magic bytes).")

    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
    except Exception as e:
        raise ValueError(f"Could not open PDF: {e}") from e

    pages_text = []
    for i, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text() or ""
            cleaned = _normalise_text(page_text)
            if cleaned:
                pages_text.append(f"[Page {i+1}]\n{cleaned}")
        except Exception:
            logger.warning("PDF: could not extract text from page %d of '%s'", i + 1, filename)

    full_text = "\n\n".join(pages_text)
    digest = _sha256(file_bytes)  # hash original bytes, not extracted text

    return ProductSourceContent(
        source_type=SourceType.PDF,
        source_name=filename,
        source_url=None,
        extracted_text=full_text,
        content_hash=digest,
        word_count=len(full_text.split()),
        char_count=len(full_text),
        metadata={"pages": len(reader.pages), "filename": filename},
    )
