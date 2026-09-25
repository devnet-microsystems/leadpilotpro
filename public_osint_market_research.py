#!/usr/bin/env python3
"""Public OSINT Market Research Aggregator.
Refactored for Multi-Engine Search and strict crawler budgeting.
"""

import os
import sqlite3
import logging
import argparse
import itertools
from typing import List, Dict
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from playwright.sync_api import sync_playwright

from osint_engine.models import UnifiedSearchResult, DiscoveredLead, QuerySpec, TargetContext, ProviderState, ProviderResult
from osint_engine.providers import DuckDuckGoProvider, BingProvider, SearXNGProvider, BraveProvider
from osint_engine.crawler import CompanyCrawler
from osint_engine.normalization import DomainClassifier
from osint_engine.strategy import QueryStrategyEngine
from osint_engine.quality import LeadScorer, AIExtractor, EmailValidator
import dataclasses

APP_NAME = "LeadPilotProOSINT"

class LeadStore:
    def __init__(self, database_path: Path):
        self.connection = sqlite3.connect(database_path)
        self.connection.execute("PRAGMA foreign_keys = ON;")
        self._init_tables()
        
    def _init_tables(self):
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS query_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                target_key TEXT,
                query_template TEXT,
                query TEXT NOT NULL,
                family TEXT NOT NULL,
                round INTEGER,
                provider TEXT NOT NULL,
                raw_results INTEGER,
                unique_domains INTEGER,
                new_domains INTEGER,
                emails_found INTEGER,
                duration_ms INTEGER,
                status TEXT DEFAULT 'SUCCESS',
                provider_state TEXT DEFAULT '',
                created_at TIMESTAMP,
                campaign_id INTEGER,
                template_id INTEGER
            )
        """)
        
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS prospects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_url TEXT NOT NULL,
                company_name TEXT NOT NULL,
                business_email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                source_file TEXT NOT NULL,
                campaign_id INTEGER,
                status TEXT NOT NULL DEFAULT 'pending_review',
                reason_for_contact TEXT NOT NULL DEFAULT '',
                imported_at_utc TEXT NOT NULL,
                approved_at_utc TEXT,
                sent_at_utc TEXT,
                message_id TEXT,
                last_error TEXT,
                email_confidence REAL,
                confidence_type TEXT,
                company_score REAL,
                contact_score REAL,
                research_campaign_id INTEGER,
                why_matched TEXT DEFAULT '',
                relevance_score REAL,
                email_quality TEXT,
                qualification_status TEXT DEFAULT 'REVIEW_REQUIRED',
                rejection_reason TEXT
            )
        """)
        
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS prospect_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prospect_id INTEGER,
                source_type TEXT,
                engine TEXT,
                source_url TEXT,
                query TEXT,
                discovered_at TEXT,
                query_run_id TEXT DEFAULT '',
                FOREIGN KEY (prospect_id) REFERENCES prospects(id)
            )
        """)
        try:
            self.connection.execute("ALTER TABLE query_runs ADD COLUMN target_key TEXT DEFAULT ''")
            self.connection.execute("ALTER TABLE query_runs ADD COLUMN query_template TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
            
        try:
            self.connection.execute("ALTER TABLE prospect_sources ADD COLUMN query_run_id TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
            
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS prospect_product_fit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prospect_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                fit_status TEXT NOT NULL,
                fit_score INTEGER DEFAULT 0,
                reason TEXT,
                matched_signals TEXT,
                missing_signals TEXT,
                negative_signals TEXT,
                evidence_source_ids TEXT,
                provider TEXT,
                model TEXT,
                created_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL,
                UNIQUE(prospect_id, product_id)
            )
        """)

        # Minimal stub so LeadStore can operate standalone (real schema owned by OutreachDatabase).
        # P5.2E: save_lead() needs to look up research_campaigns.product_id for Product Fit.
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS research_campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                product_id INTEGER,
                icp_id INTEGER,
                offer_id INTEGER,
                status TEXT DEFAULT 'DRAFT',
                created_at_utc TEXT
            )
        """)

        self.connection.commit()

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    def save_lead(self, lead: DiscoveredLead, query_run_id: str = "", research_campaign_id: int = None) -> bool:
        cursor = self.connection.cursor()
        
        # P3.1 Email Quality
        email_quality = EmailValidator.classify(lead.email, lead.email_confidence, lead.confidence_type)
        
        # P3.3 Qualification Gate
        qualification_status = 'UNQUALIFIED'
        status = 'rejected'
        rejection_reason = 'failed_gate'
        
        if email_quality == 'SUPPRESSED':
            rejection_reason = 'suppressed_email'
        elif email_quality == 'INVALID':
            rejection_reason = 'invalid_email'
            
        why_matched_text = getattr(lead, 'why_matched', '').strip()
        
        if email_quality in ('VALID', 'LIKELY_VALID', 'ROLE_BASED') and (lead.relevance_score or 0) >= 40 and lead.confidence_type != 'SYSTEM' and why_matched_text:
            qualification_status = 'QUALIFIED'
            status = 'pending_review'
            rejection_reason = None
            
        company_name = lead.company_name or lead.domain
        
        # Check if prospect exists
        existing = cursor.execute(
            "SELECT id, relevance_score, status, qualification_status, rejection_reason FROM prospects WHERE business_email = ?",
            (lead.email,)
        ).fetchone()

        if existing:
            prospect_id = existing[0]
            old_score = existing[1] or 0
            old_status = existing[2]
            old_qual = existing[3]
            old_reason = existing[4]
            is_new = False
            
            # If the new OSINT run found a better match, update the evidence and campaign
            if lead.relevance_score and lead.relevance_score > old_score:
                # Se era unqualified e ora passa il gate, riattiviamolo se non è stato gestito da un umano
                update_qual = old_qual
                update_stat = old_status
                update_rej = old_reason
                
                # Protect manual rejects
                manual_reject_reasons = {'wrong_company', 'wrong_role', 'wrong_location', 'bad_email', 'duplicate', 'not_target', 'other'}
                is_manual_reject = old_reason in manual_reject_reasons
                
                if old_qual == 'UNQUALIFIED' and qualification_status == 'QUALIFIED' and old_status == 'rejected' and not is_manual_reject:
                    update_qual = 'QUALIFIED'
                    update_stat = 'pending_review'
                    update_rej = None
                
                cursor.execute(
                    """
                    UPDATE prospects 
                    SET relevance_score = ?, 
                        why_matched = ?, 
                        research_campaign_id = COALESCE(research_campaign_id, ?),
                        email_quality = ?,
                        qualification_status = ?,
                        status = ?,
                        rejection_reason = ?
                    WHERE id = ?
                    """,
                    (lead.relevance_score, getattr(lead, 'why_matched', ''), research_campaign_id, email_quality, update_qual, update_stat, update_rej, prospect_id)
                )
        else:
            # P3.4 Account Penetration
            if research_campaign_id is not None and qualification_status == 'QUALIFIED':
                target_url_exact = f"https://{lead.domain}"
                count = cursor.execute(
                    "SELECT COUNT(*) FROM prospects WHERE target_url = ? AND research_campaign_id = ?",
                    (target_url_exact, research_campaign_id)
                ).fetchone()[0]
                if count >= 3:
                    qualification_status = 'SUPPRESSED'
                    status = 'rejected'
                    rejection_reason = 'quota_exceeded'
                    
            if research_campaign_id is not None:
                cursor.execute(
                    """
                    INSERT INTO prospects
                    (target_url, company_name, business_email, source_file, status, imported_at_utc, email_confidence, confidence_type, relevance_score, research_campaign_id, why_matched, email_quality, qualification_status, rejection_reason)
                    VALUES (?, ?, ?, 'OSINT MultiEngine', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (f"https://{lead.domain}", company_name, lead.email, status, self._utc_now(), lead.email_confidence, lead.confidence_type, lead.relevance_score, research_campaign_id, getattr(lead, 'why_matched', ''), email_quality, qualification_status, rejection_reason)
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO prospects
                    (target_url, company_name, business_email, source_file, status, imported_at_utc, email_confidence, confidence_type, relevance_score, why_matched, email_quality, qualification_status, rejection_reason)
                    VALUES (?, ?, ?, 'OSINT MultiEngine', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (f"https://{lead.domain}", company_name, lead.email, status, self._utc_now(), lead.email_confidence, lead.confidence_type, lead.relevance_score, getattr(lead, 'why_matched', ''), email_quality, qualification_status, rejection_reason)
                )
                
            prospect_id = cursor.lastrowid
            is_new = True

        # Always save source provenance
        cursor.execute(
            """
            INSERT INTO prospect_sources
            (prospect_id, source_type, engine, source_url, query, discovered_at, query_run_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (prospect_id, lead.source_type, lead.engine, lead.source_url, lead.query, self._utc_now(), query_run_id)
        )
        self.connection.commit()
        
        # --- P5.2E Product-Aware Qualification ---
        if research_campaign_id is not None:
            # Re-read to check manual rejection protection
            curr = cursor.execute("SELECT qualification_status, status, rejection_reason FROM prospects WHERE id=?", (prospect_id,)).fetchone()
            curr_qual = curr[0]
            curr_stat = curr[1]
            curr_rej = curr[2]
            
            manual_reject_reasons = {'wrong_company', 'wrong_role', 'wrong_location', 'bad_email', 'duplicate', 'not_target', 'other'}
            is_manual_reject = curr_rej in manual_reject_reasons
            
            if not is_manual_reject and (curr_qual == 'QUALIFIED' or qualification_status == 'QUALIFIED'):
                camp_row = cursor.execute("SELECT product_id FROM research_campaigns WHERE id=?", (research_campaign_id,)).fetchone()
                if camp_row and camp_row[0]:
                    product_id = camp_row[0]
                    prod_row = cursor.execute("SELECT raw_summary FROM products WHERE id=?", (product_id,)).fetchone()
                    if prod_row and prod_row[0]:
                        try:
                            import json
                            product_profile = json.loads(prod_row[0])
                            
                            from osint_engine.product_qualification import ProductQualificationAgent
                            agent = ProductQualificationAgent(str(self.connection.execute("PRAGMA database_list").fetchall()[0][2])) # Get actual db path
                            
                            prospect_evidence = {
                                "business_email": lead.email,
                                "company_name": company_name,
                                "confidence_type": lead.confidence_type,
                                "why_matched": getattr(lead, 'why_matched', ''),
                                "source_url": lead.source_url,
                                "query": lead.query
                            }
                            
                            fit_result = agent.evaluate(product_profile, prospect_evidence)
                            
                            fit_status = fit_result.get("fit_status", "REVIEW_REQUIRED")
                            fit_score = fit_result.get("fit_score", 0)
                            
                            # Do NOT overwrite prospect's base qualification_status here.
                            # It is evaluated on-the-fly in the sender side.

                            
                            # Upsert ProspectProductFit
                            now_utc = self._utc_now()
                            cursor.execute(
                                """
                                INSERT INTO prospect_product_fit 
                                (prospect_id, product_id, fit_status, fit_score, reason, matched_signals, missing_signals, negative_signals, evidence_source_ids, provider, model, created_at_utc, updated_at_utc)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ON CONFLICT(prospect_id, product_id) DO UPDATE SET
                                    fit_status=excluded.fit_status,
                                    fit_score=excluded.fit_score,
                                    reason=excluded.reason,
                                    matched_signals=excluded.matched_signals,
                                    missing_signals=excluded.missing_signals,
                                    negative_signals=excluded.negative_signals,
                                    evidence_source_ids=excluded.evidence_source_ids,
                                    provider=excluded.provider,
                                    model=excluded.model,
                                    updated_at_utc=excluded.updated_at_utc
                                """,
                                (
                                    prospect_id, product_id, fit_status, fit_score, fit_result.get("reason", ""),
                                    json.dumps(fit_result.get("matched_signals", [])),
                                    json.dumps(fit_result.get("missing_signals", [])),
                                    json.dumps(fit_result.get("negative_signals", [])),
                                    json.dumps(fit_result.get("evidence_source_ids", [])),
                                    "dynamic_provider", "dynamic_model", now_utc, now_utc
                                )
                            )
                            self.connection.commit()
                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                            print(f"Product Fit error: {e}")
                            
        return is_new

    def save_query_run(
        self, 
        run_id: str, 
        target_key: str, 
        query_template: str, 
        query: str, 
        family: str, 
        round_num: int, 
        provider: str, 
        raw_results: int, 
        unique_domains: int, 
        new_domains: int, 
        emails_found: int, 
        duration_ms: int,
        status: str = 'SUCCESS',
        provider_state: str = '',
        campaign_id: int = None,
        template_id: int = None
    ) -> int:
        cursor = self.connection.cursor()
        
        if campaign_id is not None:
            cursor.execute(
                """
                INSERT INTO query_runs
                (run_id, target_key, query_template, query, family, round, provider, raw_results, unique_domains, new_domains, emails_found, duration_ms, status, provider_state, created_at, campaign_id, template_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, target_key, query_template, query, family, round_num, provider, raw_results, unique_domains, new_domains, emails_found, duration_ms, status, provider_state, self._utc_now(), campaign_id, template_id)
            )
        else:
            cursor.execute(
                """
                INSERT INTO query_runs
                (run_id, target_key, query_template, query, family, round, provider, raw_results, unique_domains, new_domains, emails_found, duration_ms, status, provider_state, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, target_key, query_template, query, family, round_num, provider, raw_results, unique_domains, new_domains, emails_found, duration_ms, status, provider_state, self._utc_now())
            )
            
        self.connection.commit()
        return cursor.lastrowid

    def get_historical_strategies(self, target_key: str) -> Dict[str, dict]:
        cursor = self.connection.cursor()
        
        query = """
        SELECT 
            r.provider,
            r.family,
            r.query_template,
            COUNT(r.id) as query_count,
            AVG(CAST(r.new_domains AS FLOAT) / CASE WHEN r.raw_results > 0 THEN r.raw_results ELSE 1 END) as domain_yield,
            CAST(COUNT(DISTINCT s.prospect_id) AS FLOAT) / CASE WHEN COUNT(r.id) > 0 THEN COUNT(r.id) ELSE 1 END as lead_yield,
            AVG(p.relevance_score) as avg_relevance
        FROM query_runs r
        LEFT JOIN prospect_sources s ON r.run_id = s.query_run_id
        LEFT JOIN prospects p ON s.prospect_id = p.id
        WHERE r.target_key = ? AND r.status IN ('SUCCESS', 'ZERO_RESULTS')
        GROUP BY r.provider, r.family, r.query_template
        """
        
        cursor.execute(query, (target_key,))
        stats = {}
        
        for row in cursor.fetchall():
            provider, family, template, query_count, domain_yield, total_leads, avg_relevance = row
            
            lead_yield = total_leads / query_count if query_count > 0 else 0
            
            # Normalize relevance (assuming max is 100)
            quality_score = (avg_relevance or 0) / 100.0
            
            # Domain yield score (cap at 5 domains per query for normalization)
            domain_yield_score = min(1.0, (domain_yield or 0) / 5.0)
            
            # Lead yield score (cap at 5 leads per query for normalization)
            lead_yield_score = min(1.0, (lead_yield or 0) / 5.0)
            
            # Composite performance score (0 to 100)
            performance_score = (0.50 * quality_score + 0.30 * lead_yield_score + 0.20 * domain_yield_score) * 100
            
            key = f"{provider}|{family}|{template}"
            stats[key] = {
                "query_count": query_count,
                "domain_yield": domain_yield or 0,
                "lead_yield": lead_yield,
                "avg_relevance": avg_relevance or 0,
                "performance_score": performance_score
            }
            
        return stats

    def close(self):
        self.connection.close()

def parse_args():
    parser = argparse.ArgumentParser(description="Multi-engine OSINT Lead Discovery")
    parser.add_argument("--database", default="outreach_queue.sqlite3")
    parser.add_argument("--results-per-query", type=int, default=10)
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--headed", action="store_true")
    
    # Structured Mode
    parser.add_argument("--role", default="")
    parser.add_argument("--industry", default="")
    parser.add_argument("--location", default="")
    parser.add_argument("--country", default="")
    
    # LeadPilot 2.0 Campaign Mode
    parser.add_argument("--campaign-id", type=int, default=None)
    
    # Legacy / Seed Mode
    parser.add_argument("--queries", nargs="*", default=[])
    parser.add_argument("--max-queries", type=int, default=0) # Legacy
    
    # Budget configuration
    parser.add_argument("--max-leads", type=int, default=150, help="Maximum number of leads to discover before stopping")
    
    # Quick Search Mode
    parser.add_argument("--quick-search", action="store_true", help="Run without saving to DB and output JSON")
    
    return parser.parse_args()

def main():
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s %(levelname)s %(message)s")
    
    database_path = Path(args.database).expanduser().resolve()
    
    conn = None
    try:
        conn = sqlite3.connect(database_path)
        conn.row_factory = sqlite3.Row
        if args.queries:
            raw_queries = args.queries
        else:
            if not any([args.role, args.industry, args.location, args.country, args.campaign_id, args.quick_search]):
                # If neither mode is used, read from DB
                raw_queries = [row["query"] for row in conn.execute("SELECT query FROM research_queries").fetchall()]
            else:
                raw_queries = []
    except Exception as exc:
        logging.error(f"DB load error: {exc}")
        return 2

    if args.max_queries and raw_queries:
        raw_queries = raw_queries[:args.max_queries]

    providers = {
        "DuckDuckGoProvider": DuckDuckGoProvider(),
        "BingProvider": BingProvider(),
        "SearXNGProvider": SearXNGProvider(),
        "BraveProvider": BraveProvider()
    }
    
    active_providers = [p for p in providers.values() if p.enabled]
    active_provider_names = [p.name for p in active_providers]
    logging.info(f"Active providers: {active_provider_names}")

    store = LeadStore(database_path)
    target_ctx = TargetContext(
        role=args.role or "",
        industry=args.industry or "",
        location=args.location or "",
        country=args.country or ""
    )
    
    pregenerated_specs = None
    if args.campaign_id:
        c = conn.cursor()
        c.row_factory = sqlite3.Row
        
        # Load Campaign and ICP to build context
        camp = c.execute("SELECT icp_id, offer_id FROM research_campaigns WHERE id=?", (args.campaign_id,)).fetchone()
        if camp:
            icp = c.execute("SELECT * FROM ideal_customer_profiles WHERE id=?", (camp["icp_id"],)).fetchone()
            if icp:
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
                    role=", ".join(roles) if roles else target_ctx.role,
                    industry=", ".join(industries) if industries else target_ctx.industry,
                    location=", ".join(locations) if locations else target_ctx.location,
                    country=", ".join(countries) if countries else target_ctx.country
                )
        
        c.execute("SELECT * FROM campaign_queries WHERE campaign_id=? AND is_enabled=1", (args.campaign_id,))
        concrete_queries = [dict(r) for r in c.fetchall()]
        
        pregenerated_specs = []
        for cq in concrete_queries:
            for p in active_provider_names:
                pregenerated_specs.append(QuerySpec(
                    text=cq["query"],
                    family=cq["family"],
                    round=0,
                    priority=1.0,
                    template="",  # We store template_id in template field for now, to map it later
                    provider_name=p
                ))
    
    historical_stats = store.get_historical_strategies(target_ctx.target_key)
    
    engine = QueryStrategyEngine(
        target_ctx=target_ctx,
        seed_queries=raw_queries,
        active_providers=active_provider_names,
        historical_stats=historical_stats,
        pregenerated_specs=pregenerated_specs
    )
    
    all_rounds = engine.generate_all_rounds()
        
    crawler = CompanyCrawler(
        role=args.role,
        industry=args.industry,
        location=args.location,
        campaign_id=args.campaign_id,
        db_path=str(database_path)
    )
    
    # Metrics Tracking
    metrics = {
        "raw_results": 0,
        "unique_urls": set(),
        "unique_domains": set(),
        "blocked_domains": set(),
        "crawled_pages": 0,
        "emails_found": set(),
        "unique_emails": set(),
        "leads_inserted": 0,
        "provider_stats": {},
        "queries_executed": 0,
        "quality_breakdown": {
            "PERSONAL": 0,
            "ROLE_BASED": 0,
            "PERSONAL_EMAIL_PROVIDER": 0,
            "SYSTEM": 0,
            "INVALID": 0
        },
        "relevance_breakdown": {
            "High": 0,
            "Medium": 0,
            "Low": 0
        }
    }
    
    for p in providers.values():
        metrics["provider_stats"][p.name] = {"status": "OFF" if not p.enabled else "OK", "results": 0, "error": ""}

    provider_failures = {p_name: 0 for p_name in providers.keys()}
    provider_cooldown_until = {p_name: 0.0 for p_name in providers.keys()}
    PROVIDER_MIN_DELAY = float(os.getenv("PROVIDER_MIN_DELAY", "2.0"))
    PROVIDER_MAX_DELAY = float(os.getenv("PROVIDER_MAX_DELAY", "5.0"))

    start_time = datetime.now()

    MIN_NEW_DOMAINS = 1
    MIN_NEW_EMAILS = 2
    MIN_NEW_TARGET_PAGES = 2
    MAX_ROUNDS = 4
    MAX_TOTAL_QUERIES = args.max_queries if args.max_queries > 0 else 30
    MAX_TOTAL_LEADS = args.max_leads
    
    global_domains_seen = set()
    total_queries_executed = 0
    run_batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    adaptive_report = []

    quick_search_results = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()

        for round_num in sorted(all_rounds.keys()):
            if round_num > MAX_ROUNDS:
                break
                
            round_specs = all_rounds[round_num]
            if not round_specs:
                continue
                
            round_specs = sorted(round_specs, key=lambda x: x.priority, reverse=True)
            
            round_raw_results = 0
            round_unique_domains = set()
            round_new_domains = 0
            round_new_emails = 0
            round_new_target_pages = 0
            round_queries_executed = 0
            
            logging.info(f"\n--- [ROUND {round_num}] ---")
            
            for spec in round_specs:
                if total_queries_executed >= MAX_TOTAL_QUERIES:
                    logging.info("MAX_TOTAL_QUERIES reached, stopping round.")
                    break
                if metrics["leads_inserted"] >= MAX_TOTAL_LEADS:
                    logging.info(f"MAX_TOTAL_LEADS ({MAX_TOTAL_LEADS}) reached, stopping round.")
                    break
                    
                # Provider routing
                provider = providers.get(spec.provider_name)
                if not provider or not provider.enabled:
                    logging.warning(f"Skipping {spec.text} - provider {spec.provider_name} not available")
                    continue
                    
                import time
                if time.time() < provider_cooldown_until.get(provider.name, 0):
                    logging.warning(f"Skipping provider {provider.name} due to cooldown.")
                    continue
                    
                logging.info(f"Executing: {spec.text} (Family: {spec.family}, Provider: {provider.name})")
                adaptive_report.append({
                    "strategy": f"{provider.name} / {spec.family} / {spec.template}",
                    "samples": spec.samples,
                    "score": spec.priority,
                    "type": "EXPLORATION" if spec.is_exploration else "EXPLOITATION"
                })
                
                total_queries_executed += 1
                round_queries_executed += 1
                
                query_run_id = f"{run_batch_id}_{total_queries_executed}"
                
                import random
                delay = random.uniform(PROVIDER_MIN_DELAY, PROVIDER_MAX_DELAY)
                time.sleep(delay)
                
                all_results = []
                query_start = datetime.now()
                db_status = 'SUCCESS'
                provider_state_str = ''
                
                try:
                    adapted_query = provider.adapt_query(spec)
                    provider_result = provider.search(query=adapted_query, limit=args.results_per_query, page=page, country=target_ctx.country)
                    results = provider_result.results
                    provider_state_str = provider_result.status.name
                    
                    if provider_result.status in (ProviderState.BLOCKED, ProviderState.RATE_LIMITED):
                        logging.warning(f"  {provider.name} returned {provider_result.status.name}. Triggering cooldown.")
                        provider_cooldown_until[provider.name] = time.time() + 300 # 5 min cooldown
                        db_status = 'PROVIDER_FAILURE'
                    elif provider_result.status in (ProviderState.DEGRADED, ProviderState.ERROR):
                        provider_failures[provider.name] += 1
                        logging.warning(f"  {provider.name} degraded ({provider_failures[provider.name]}/3 failures).")
                        if provider_failures[provider.name] >= 3:
                            logging.error(f"  {provider.name} reached max failures. Triggering cooldown.")
                            provider_cooldown_until[provider.name] = time.time() + 300
                            provider_failures[provider.name] = 0
                        db_status = 'PROVIDER_FAILURE'
                    elif provider_result.status == ProviderState.ZERO_RESULTS:
                        provider_failures[provider.name] = 0
                        db_status = 'ZERO_RESULTS'
                    else:
                        provider_failures[provider.name] = 0
                        db_status = 'SUCCESS'
                    
                    if provider_result.error:
                        metrics["provider_stats"][provider.name]["error"] = provider_result.error

                    metrics["provider_stats"][provider.name]["results"] += len(results)
                    all_results.extend(results)
                    if results:
                        logging.debug(f"  {provider.name}: {len(results)} results")
                except Exception as e:
                    metrics["provider_stats"][provider.name]["status"] = "FAIL"
                    metrics["provider_stats"][provider.name]["error"] = str(e)
                    logging.error(f"  {provider.name} failed: {e}")
                    db_status = 'PROVIDER_FAILURE'
                    provider_state_str = 'EXCEPTION'

                metrics["raw_results"] += len(all_results)
                round_raw_results += len(all_results)
                
                domain_map: Dict[str, UnifiedSearchResult] = {}
                for res in all_results:
                    metrics["unique_urls"].add(res.url)
                    if DomainClassifier.is_allowed(res.domain):
                        metrics["unique_domains"].add(res.domain)
                        round_unique_domains.add(res.domain)
                        if res.domain not in domain_map:
                            domain_map[res.domain] = res
                    else:
                        metrics["blocked_domains"].add(res.domain)
                        
                unique_results = []
                seen_urls_in_query = set()
                for res in all_results:
                    if res.url not in seen_urls_in_query:
                        seen_urls_in_query.add(res.url)
                        unique_results.append(res)
                
                query_new_domains = 0
                query_new_emails = 0
                query_new_target_pages = 0
                
                for res in unique_results:
                    if not DomainClassifier.is_allowed(res.domain):
                        continue
                        
                    if res.domain not in global_domains_seen:
                        global_domains_seen.add(res.domain)
                        round_new_domains += 1
                        query_new_domains += 1
                        
                    if res.url not in crawler.visited_urls:
                        round_new_target_pages += 1
                        query_new_target_pages += 1
                        
                        leads = crawler.crawl(page, res.url, res.domain, res.engine, spec.text)
                        
                        for lead in leads:
                            # 1. Relevance Score
                            score, _ = LeadScorer.calculate_score(
                                email=lead.email, 
                                confidence_type=lead.confidence_type, 
                                page_title=res.title, 
                                context_text=res.snippet, 
                                role=target_ctx.role, 
                                industry=target_ctx.industry, 
                                location=target_ctx.location
                            )
                            
                            # 2. AI Qualification
                            reason = ""
                            if score >= 40:
                                reason = AIExtractor.generate_why_matched(
                                    db_path=str(database_path),
                                    campaign_id=args.campaign_id,
                                    lead_email=lead.email,
                                    page_title=res.title,
                                    context_text=res.snippet
                                )
                            
                            qualified_lead = dataclasses.replace(lead, relevance_score=score, why_matched=reason)
                            
                            if args.quick_search:
                                quick_search_results.append(dataclasses.asdict(qualified_lead))
                                is_new = True
                            else:
                                is_new = store.save_lead(qualified_lead, query_run_id=query_run_id, research_campaign_id=args.campaign_id)
                            
                            if is_new:
                                query_new_emails += 1
                                round_new_emails += 1
                                metrics["leads_inserted"] += 1
                                metrics["emails_found"].add(lead.email)
                                metrics["unique_emails"].add(lead.email)
                                
                                metrics["quality_breakdown"][lead.confidence_type] = metrics["quality_breakdown"].get(lead.confidence_type, 0) + 1
                                if lead.relevance_score >= 70:
                                    metrics["relevance_breakdown"]["High"] += 1
                                elif lead.relevance_score >= 40:
                                    metrics["relevance_breakdown"]["Medium"] += 1
                                else:
                                    metrics["relevance_breakdown"]["Low"] += 1
                                
                logging.info(f"  > Unique domains: {len(domain_map)} | New domains: {query_new_domains}")
                query_end = datetime.now()
                duration_ms = int((query_end - query_start).total_seconds() * 1000)
                
                template_id_val = None
                query_template_str = spec.template
                if args.campaign_id and spec.template.isdigit():
                    template_id_val = int(spec.template)
                    query_template_str = "" # The UI can join with query_templates to get the string
                
                if not args.quick_search:
                    store.save_query_run(
                        run_id=query_run_id,
                        target_key=target_ctx.target_key,
                        query_template=query_template_str,
                        query=spec.text,
                        family=spec.family,
                        round_num=round_num,
                        provider=provider.name,
                        raw_results=len(all_results),
                        unique_domains=len(domain_map),
                        new_domains=query_new_domains,
                        emails_found=query_new_emails,
                        duration_ms=duration_ms,
                        status=db_status,
                        provider_state=provider_state_str,
                        campaign_id=args.campaign_id,
                        template_id=template_id_val
                    )
                
            if total_queries_executed >= MAX_TOTAL_QUERIES:
                break
                
            if metrics["leads_inserted"] >= MAX_TOTAL_LEADS:
                logging.info(f"MAX_TOTAL_LEADS ({MAX_TOTAL_LEADS}) reached, stopping overall execution.")
                break
                
            if round_queries_executed > 0:
                domain_yield_per_query = round_new_domains / round_queries_executed
                email_yield_per_query = round_new_emails / round_queries_executed
            else:
                domain_yield_per_query = 0
                email_yield_per_query = 0
                
            decision = "CONTINUE"
            if round_raw_results == 0:
                decision = "STOP (SEARCH_INFRASTRUCTURE_FAILURE / 0 Raw Results)"
            elif round_new_domains < MIN_NEW_DOMAINS and round_new_emails < MIN_NEW_EMAILS and round_new_target_pages < MIN_NEW_TARGET_PAGES:
                decision = "STOP (Niche exhausted / threshold met)"
                
            logging.info(f"Round {round_num} Summary:")
            logging.info(f"Queries: {round_queries_executed}")
            logging.info(f"Raw results: {round_raw_results}")
            logging.info(f"Unique domains: {len(round_unique_domains)}")
            logging.info(f"New domains: {round_new_domains}")
            logging.info(f"New emails: {round_new_emails}")
            logging.info(f"New target pages: {round_new_target_pages}")
            logging.info(f"Domain yield/query: {domain_yield_per_query:.2f}")
            logging.info(f"Email yield/query: {email_yield_per_query:.2f}")
            logging.info(f"Decision: {decision}")
            
            if "STOP" in decision:
                break

        browser.close()
        
    metrics["crawled_pages"] = crawler.pages_crawled_this_run
    metrics["queries_executed"] = total_queries_executed
    elapsed = (datetime.now() - start_time).total_seconds()
        
    store.close()
    if conn:
        conn.close()

    logging.info("\n" + "="*40)
    logging.info("FINAL METRICS REPORT")
    logging.info("="*40)
    logging.info("Providers:")
    for p_name, p_stat in metrics["provider_stats"].items():
        if p_stat["status"] == "FAIL":
            logging.info(f"  {p_name:15} {p_stat['status']:4} {p_stat['error']}")
        else:
            logging.info(f"  {p_name:15} {p_stat['status']:4} {p_stat['results']} results")
            
    logging.info("\nAdaptive Strategy Report:")
    logging.info(f"Target: {target_ctx.target_key}")
    exploration_count = 0
    exploitation_count = 0
    for rep in adaptive_report:
        if rep['type'] == 'EXPLORATION':
            exploration_count += 1
        else:
            exploitation_count += 1
        score_source = "HISTORY" if rep['type'] == 'EXPLOITATION' else "PRIOR"
        logging.info(f"  {rep['strategy']:<55} | Samples: {rep['samples']:>3} | Score: {rep['score']:>6.2f} ({score_source:<7}) | {rep['type']}")
    logging.info(f"Exploration: {exploration_count} queries")
    logging.info(f"Exploitation: {exploitation_count} queries")
            
    logging.info(f"\nQueries Executed:   {metrics['queries_executed']}")
    logging.info(f"Raw results:        {metrics['raw_results']}")
    logging.info(f"Unique URLs:        {len(metrics['unique_urls'])}")
    logging.info(f"Unique domains:     {len(metrics['unique_domains'])}")
    logging.info(f"Blocked domains:    {len(metrics['blocked_domains'])}")
    logging.info(f"Crawled pages:      {crawler.pages_crawled_this_run}")
    logging.info(f"Unique emails:      {len(metrics['unique_emails'])}")
    logging.info(f"Leads inserted:     {metrics['leads_inserted']}")
    logging.info(f"Elapsed time:       {(datetime.now() - start_time).total_seconds():.2f}s")
    
    logging.info("\nLead Quality Breakdown:")
    logging.info(f"  Personal contacts:       {metrics['quality_breakdown'].get('PERSONAL', 0)}")
    logging.info(f"  Role-based:              {metrics['quality_breakdown'].get('ROLE_BASED', 0)}")
    logging.info(f"  Personal email provider: {metrics['quality_breakdown'].get('PERSONAL_EMAIL_PROVIDER', 0)}")
    logging.info(f"  System/Invalid:          {metrics['quality_breakdown'].get('SYSTEM', 0) + metrics['quality_breakdown'].get('INVALID', 0)}")
    
    logging.info("\nRelevance:")
    logging.info(f"  High (>= 70): {metrics['relevance_breakdown']['High']}")
    logging.info(f"  Medium (40-69): {metrics['relevance_breakdown']['Medium']}")
    logging.info(f"  Low (< 40): {metrics['relevance_breakdown']['Low']}")
    
    logging.info("========================================\n")

    if args.quick_search:
        import json
        # Output the JSON array of leads to stdout and exit
        print("QUICK_SEARCH_RESULTS_START")
        print(json.dumps(quick_search_results, indent=2))
        print("QUICK_SEARCH_RESULTS_END")


if __name__ == "__main__":
    raise SystemExit(main())
