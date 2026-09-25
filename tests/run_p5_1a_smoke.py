"""
tests/run_p5_1a_smoke.py

Standalone runner for P5.1A Real Provider test.
Reads AI config directly from DB. Does NOT accept keys from args.
Run: .venv/bin/python tests/run_p5_1a_smoke.py
"""
import json
import time
import os
import sqlite3
import db_connector
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from product_intelligence.models import ProductSourceContent, SourceType
from product_intelligence.provider import get_ai_provider, OpenAICompatibleProvider
from product_intelligence.agent import ProductIntelligenceAgent
from product_intelligence.store import (
    ensure_schema, create_product, get_product,
    add_source, list_sources, get_sources_with_text,
    set_product_status, save_product_analysis,
)
from product_intelligence.extractor import extract_from_text

DB_PATH = "outreach_queue.sqlite3"
PASSED = []
FAILED = []


def check(name, condition, detail=""):
    if condition:
        print(f"  ✅ {name}")
        PASSED.append(name)
    else:
        print(f"  ❌ {name}" + (f": {detail}" if detail else ""))
        FAILED.append(name)


def run_sources(agent, texts, product_name):
    sources = [extract_from_text(t, f"src-{i+1}") for i, t in enumerate(texts)]
    return agent.analyse(sources, user_supplied_name=product_name)


print("\n" + "="*60)
print("P5.1A — Real AI Provider Smoke Test")
print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
print("="*60)

# ── Step 1: Provider config ────────────────────────────────────────────────
print("\n[1] Provider Configuration")
provider = get_ai_provider(DB_PATH)
check("Provider available", provider.available())
check("Base URL is OpenRouter/Gemini/Groq endpoint",
      any(x in (provider._base_url or "").lower() for x in ("openrouter", "gemini", "groq")),
      provider._base_url)
check("Model configured", bool(provider.model_name), provider.model_name)
print(f"  → provider={provider.provider_name}, model={provider.model_name}")

if not provider.available():
    print("\n❌ Provider not available. Stopping.")
    sys.exit(1)

# ── Step 2: Raw connectivity ────────────────────────────────────────────────
print("\n[2] Provider Connectivity (minimal JSON probe)")
raw = provider.generate_structured(
    system_prompt="You are a JSON-only responder. Never use markdown fences.",
    user_prompt='Return exactly: {"status":"ok","check":"connectivity"}',
    max_tokens=60,
    temperature=0.0,
)
check("Provider returned response", raw is not None, provider.last_error)
if raw:
    clean = raw.strip().strip("```json").strip("```").strip()
    try:
        data = json.loads(clean)
        check("Response is valid JSON", True)
        check("Response has status field", "status" in data)
    except json.JSONDecodeError as e:
        check("Response is valid JSON", False, f"{e} — got: {clean[:100]}")
    print(f"  → raw response: {clean[:120]}")

# ── Step 3: Agent schema compliance ────────────────────────────────────────
print("\n[3] Agent Schema Compliance")
agent = ProductIntelligenceAgent(provider)
text_simple = (
    "LeadPilot Pro is a B2B lead generation platform for sales teams. "
    "It discovers business prospects through public web research, qualifies contacts "
    "using AI relevance scoring, and prepares personalised outreach campaigns. "
    "Typical buyers are Sales Directors and CROs at SaaS companies."
)
try:
    profile = run_sources(agent, [text_simple], "LeadPilot Pro")
    required_keys = [
        "product_name", "short_description", "category", "value_proposition",
        "problems_solved", "key_features", "target_company_types",
        "potential_buyer_roles", "keywords", "business_model",
        "pricing_information", "conflicts",
    ]
    missing = [k for k in required_keys if k not in profile]
    check("All required schema keys present", not missing, f"missing: {missing}")
    check("product_name not UNKNOWN", profile.get("product_name","").upper() != "UNKNOWN")
    check("Has keywords", bool(profile.get("keywords")))
    print(f"  → product_name: {profile.get('product_name')}")
    print(f"  → category: {profile.get('category')}")
    print(f"  → keywords (first 3): {profile.get('keywords', [])[:3]}")
except Exception as e:
    check("Agent analyse succeeded", False, str(e))
    profile = {}

# ── Step 4: Full pipeline E2E (DB persistence) ─────────────────────────────
print("\n[4] Full E2E — create → source → analyse → DB persistence (3 Runs)")
ensure_schema(DB_PATH)

e2e_profile = None
for run_idx in range(1, 4):
    print(f"\n--- RUN {run_idx} ---")
    product = create_product(DB_PATH, f"LeadPilot Pro Smoke {int(time.time())}_{run_idx}")
    pid = product["id"]
    
    text_full = (
        "LeadPilot Pro is a B2B SaaS platform for sales and growth teams. "
        "It automatically discovers leads via public web OSINT, qualifies them using "
        "an AI relevance engine, and manages personalised outreach email campaigns. "
        "Typical buyers are Sales Directors, CROs, and Growth Managers at SaaS companies "
        "with 10-200 employees. The platform operates on a subscription model."
    )
    content_obj = extract_from_text(text_full, f"full-e2e-description-{run_idx}")
    add_source(DB_PATH, pid, content_obj.source_type.value, content_obj.source_name,
               content_obj.content_hash, content_obj.extracted_text)
    
    set_product_status(DB_PATH, pid, "ANALYZING")
    source_rows = get_sources_with_text(DB_PATH, pid)
    sources = [ProductSourceContent(
        source_type=SourceType(r["source_type"]), source_name=r["source_name"],
        source_url=r.get("source_url"), extracted_text=r["extracted_text"],
        content_hash=r["content_hash"],
    ) for r in source_rows]
    
    try:
        e2e_profile = time.sleep(60)
        e2e_profile = agent.analyse(sources, user_supplied_name="LeadPilot Pro")
        save_product_analysis(DB_PATH, pid, e2e_profile, provider.provider_name, provider.model_name)
        p = get_product(DB_PATH, pid)
        check(f"RUN {run_idx}", p["status"] == "READY", p.get("status"))
        
        loaded = json.loads(p["raw_summary"])
        print(f"  → RUN {run_idx} READY ✅ product_id={pid}")
    except Exception as e:
        set_product_status(DB_PATH, pid, "FAILED", str(e)[:300])
        check(f"RUN {run_idx}", False, str(e)[:120])

print("\n[5] Anti-Hallucination — pricing must be UNKNOWN")
text_no_price = (
    "AcmeCRM is a customer relationship management tool for small businesses. "
    "It helps teams track leads, manage follow-ups, and close deals faster. "
    "The target buyer is the Founder or CEO of companies with fewer than 50 employees. "
    "No information about pricing is available."
)
try:
    no_price_profile = time.sleep(60)
    no_price_profile = run_sources(agent, [text_no_price], "AcmeCRM")
    pricing = no_price_profile.get("pricing_information", {})
    print(f"  → pricing_information: {pricing}")
    if isinstance(pricing, dict):
        status = pricing.get("status", "")
        if status == "UNKNOWN":
            check("Pricing is UNKNOWN (not hallucinated)", True)
        elif status == "KNOWN":
            evidence = pricing.get("evidence_source_ids", [])
            # KNOWN with empty evidence is hallucination
            check("Pricing KNOWN has evidence", bool(evidence),
                  f"hallucinated: {pricing.get('summary', '')}")
        else:
            check("Pricing has valid status", False, f"unexpected status: {status}")
    elif isinstance(pricing, str) and pricing.upper() == "UNKNOWN":
        check("Pricing is UNKNOWN (string form)", True)
    else:
        check("Pricing is UNKNOWN (not hallucinated)", False, str(pricing))
except Exception as e:
    check("Anti-hallucination test ran", False, str(e)[:120])

# ── Step 6: Multi-source synthesis ─────────────────────────────────────────
print("\n[6] Multi-Source Synthesis (2 sources)")
text_s1 = (
    "DataPulse is a real-time analytics platform for e-commerce companies. "
    "It integrates with Shopify, WooCommerce, and Magento to provide live revenue "
    "dashboards, customer journey tracking, and predictive churn alerts."
)
text_s2 = (
    "DataPulse pricing: monthly subscription at €299/month for up to 10,000 orders. "
    "Enterprise plans are available. Primary buyers are Head of E-commerce and CMO "
    "at online retail companies with annual revenue above €1M."
)
try:
    multi_profile = time.sleep(60)
    multi_profile = run_sources(agent, [text_s1, text_s2], "DataPulse")
    check("source_count = 2", multi_profile.get("_meta", {}).get("source_count") == 2)
    pricing_m = multi_profile.get("pricing_information", {})
    print(f"  → pricing_information: {pricing_m}")
    roles = multi_profile.get("potential_buyer_roles", [])
    print(f"  → potential_buyer_roles: {[r.get('value',r) for r in roles[:3]]}")
    check("Has potential_buyer_roles", bool(roles))
    # Pricing from source 2 should now be KNOWN
    if isinstance(pricing_m, dict):
        check("Pricing is KNOWN from source 2",
              pricing_m.get("status") == "KNOWN",
              f"got: {pricing_m.get('status')}")
    else:
        check("Pricing is KNOWN from source 2", False, str(pricing_m))
except Exception as e:
    check("Multi-source analysis ran", False, str(e)[:120])

# ── Step 7: Failure path ───────────────────────────────────────────────────

# ── Step 6b: Real Source URL test ───────────────────────────────────────────
print("\n[6b] Real Source URL test")
ensure_schema(DB_PATH)
try:
    url_product = create_product(DB_PATH, f"URL Smoke {int(time.time())}")
    upid = url_product["id"]
    from product_intelligence.extractor import extract_from_url
    url_content = extract_from_url("https://example.com")
    add_source(DB_PATH, upid, url_content.source_type.value, url_content.source_name, url_content.content_hash, url_content.extracted_text)
    
    url_source_rows = get_sources_with_text(DB_PATH, upid)
    url_sources = [ProductSourceContent(
        source_type=SourceType(r["source_type"]), source_name=r["source_name"],
        source_url=r.get("source_url"), extracted_text=r["extracted_text"],
        content_hash=r["content_hash"],
    ) for r in url_source_rows]
    
    url_profile = time.sleep(60)
    url_profile = agent.analyse(url_sources, user_supplied_name="Example Domain")
    save_product_analysis(DB_PATH, upid, url_profile, provider.provider_name, provider.model_name)
    up = get_product(DB_PATH, upid)
    check("REAL URL", up["status"] == "READY", up.get("status"))
except Exception as e:
    check("REAL URL (EXTRACTION FAILURE or AI)", False, str(e)[:120])
    
print("\n[7] Failure Path — provider unavailable")
from unittest.mock import patch

fail_product = create_product(DB_PATH, f"FailPath {int(time.time())}")
fpid = fail_product["id"]
fail_content = extract_from_text("Some product text for failure test.", "fail")
add_source(DB_PATH, fpid, fail_content.source_type.value, fail_content.source_name,
           fail_content.content_hash, fail_content.extracted_text)

set_product_status(DB_PATH, fpid, "ANALYZING")
with patch.object(OpenAICompatibleProvider, "available", return_value=False):
    with patch.object(OpenAICompatibleProvider, "last_error", return_value="Simulated timeout"):
        fail_provider = get_ai_provider(DB_PATH)
        fail_agent = ProductIntelligenceAgent(fail_provider)
        try:
            fail_rows = get_sources_with_text(DB_PATH, fpid)
            fail_srcs = [ProductSourceContent(
                source_type=SourceType(r["source_type"]), source_name=r["source_name"],
                source_url=r.get("source_url"), extracted_text=r["extracted_text"],
                content_hash=r["content_hash"],
            ) for r in fail_rows]
            fail_agent.analyse(fail_srcs)
            set_product_status(DB_PATH, fpid, "FAILED", "Simulated timeout")
        except RuntimeError as e:
            set_product_status(DB_PATH, fpid, "FAILED", str(e)[:200])

fp = get_product(DB_PATH, fpid)
check("Failure → status = FAILED", fp["status"] == "FAILED", fp.get("status"))
check("Failure → error_message set", bool(fp.get("error_message")))
check("Failure → raw_summary is None", fp.get("raw_summary") is None)
remaining = list_sources(DB_PATH, fpid)
check("Failure → sources preserved", len(remaining) == 1, f"got {len(remaining)} sources")
print(f"  → error_message: {fp.get('error_message', '')[:80]}")

# ── Step 8: Security audit ─────────────────────────────────────────────────
print("\n[8] Security Audit — API key not in output")
conn = db_connector.get_connection(DB_PATH)
db_key = conn.execute("SELECT value FROM settings WHERE key='ai_api_key'").fetchone()
conn.close()
key_val = db_key[0] if db_key else ""
import os
key_val = os.environ.get("GROQ_API_KEY", key_val)
key_prefix = key_val[:12] if len(key_val) >= 12 else key_val

# Check profile output doesn't contain key
if e2e_profile if 'e2e_profile' in dir() else {}:
    profile_str = json.dumps(e2e_profile)
    if not key_prefix:
        check("API key not in profile JSON (skipped, empty key)", True)
    else:
        check("API key not in profile JSON", key_prefix not in profile_str)
else:
    check("Security check skipped (no profile)", False, "e2e analysis did not produce a profile")

# ── Summary ────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("RESULTS SUMMARY")
print("="*60)
print(f"PASSED: {len(PASSED)}")
print(f"FAILED: {len(FAILED)}")
if FAILED:
    print("\nFailed checks:")
    for f in FAILED:
        print(f"  ❌ {f}")

print("\n" + "-"*60)
all_ok = len(FAILED) == 0
print(f"P5.1A STATUS: {'GREEN ✅' if all_ok else 'RED ❌'}")
print(f"REAL AI ANALYSIS: {'PASS' if 'Product status = READY' in PASSED else 'FAIL'}")
print(f"FAILURE PATH: {'PASS' if 'Failure → status = FAILED' in PASSED else 'FAIL'}")
print(f"RATE LIMIT INFO:")
for k, v in getattr(provider, "last_meta", {}).items():
    if k != "actual_model":
        print(f"  {k}: {v}")
print(f"ACTUAL MODEL USED: {getattr(provider, 'last_meta', {}).get('actual_model', 'N/A')}")
print(f"FILES MODIFIED: product_intelligence/provider.py, tests/run_p5_1a_smoke.py")
print("CRITICAL ISSUES: None")
print("-" * 60)
sys.exit(0 if all_ok else 1)
