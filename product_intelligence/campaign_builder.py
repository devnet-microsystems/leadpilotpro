import json
import sqlite3
import db_connector
import time
from typing import Optional
from datetime import datetime, timezone

def create_campaign_from_product(db_path: str, product_id: int) -> Optional[int]:
    """
    Reads a ProductProfile from the database, builds an IdealCustomerProfile,
    SalesOffer, ResearchCampaign, and injects custom search query templates
    tailored to the product's keywords and buyer roles.
    
    Returns the newly created campaign_id, or None if the product doesn't have a valid profile.
    """
    conn = db_connector.get_connection(db_path)
    conn.row_factory = sqlite3.Row
    
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product or product["status"] != "READY" or not product["raw_summary"]:
        conn.close()
        return None
        
    try:
        profile = json.loads(product["raw_summary"])
    except json.JSONDecodeError:
        conn.close()
        return None
        
    now = datetime.now(timezone.utc).isoformat()
    product_name = profile.get("product_name", product["name"])
    
    # 1. Identity & Idempotency Check
    camp_name = f"[Auto] Discovery: Product {product_id}"
    
    # 2. Extract Data from Profile (No UNKNOWN leakage)
    def _extract_values(item_list):
        if not item_list: return []
        res = []
        for item in item_list:
            if isinstance(item, dict) and item.get("value"):
                res.append(item["value"])
            elif isinstance(item, str):
                res.append(item)
        return res

    roles = _extract_values(profile.get("potential_buyer_roles", []))
    if not roles: roles = ["Decision Maker"]
    
    company_types = _extract_values(profile.get("target_company_types", []))
    industries = _extract_values(profile.get("target_industries", []))
    
    raw_markets = _extract_values(profile.get("geographic_markets", []))
    
    MARKET_MAP = {
        "italy": ("Italy", "Italian"),
        "italia": ("Italy", "Italian"),
        "it": ("Italy", "Italian"),
        "spain": ("Spain", "Spanish"),
        "españa": ("Spain", "Spanish"),
        "es": ("Spain", "Spanish"),
        "united states": ("United States", "English"),
        "usa": ("United States", "English"),
        "us": ("United States", "English"),
        "germany": ("Germany", "German"),
        "france": ("France", "French"),
        "uk": ("United Kingdom", "English"),
        "united kingdom": ("United Kingdom", "English"),
    }
    
    normalized_markets = []
    normalized_languages = []
    
    if raw_markets:
        for m in raw_markets:
            key = str(m).strip().lower()
            if key in MARKET_MAP:
                country, lang = MARKET_MAP[key]
                if country not in normalized_markets:
                    normalized_markets.append(country)
                if lang not in normalized_languages:
                    normalized_languages.append(lang)
            else:
                if m not in normalized_markets:
                    normalized_markets.append(m)
    else:
        # We DO NOT use "Global" anymore, but if empty, we leave it empty to avoid "UNKNOWN" leakage
        pass
        
    existing = conn.execute("SELECT id, icp_id, offer_id FROM research_campaigns WHERE name = ?", (camp_name,)).fetchone()
    if existing:
        campaign_id = existing["id"]
        icp_id = existing["icp_id"]
        # Update existing ICP incrementally
        conn.execute(
            "UPDATE ideal_customer_profiles SET roles=?, industries=?, countries=?, languages=? WHERE id=?",
            (json.dumps(roles), json.dumps(industries) if industries else '[]', json.dumps(normalized_markets), json.dumps(normalized_languages), icp_id)
        )
    else:
        # Create ICP
        icp_name = f"[Auto] ICP: Product {product_id}"
        conn.execute(
            "INSERT INTO ideal_customer_profiles (name, roles, industries, company_sizes, countries, languages, created_at_utc) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (icp_name, json.dumps(roles), json.dumps(industries) if industries else '[]', "Any", json.dumps(normalized_markets), json.dumps(normalized_languages), now)
        )
        icp_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        # Create SalesOffer
        price = profile.get("pricing_information", {}).get("summary", "")
        offer_name = f"[Auto] Offer: Product {product_id}"
        conn.execute(
            "INSERT INTO sales_offers (name, description, price, target_buyer_roles, created_at_utc) VALUES (?, ?, ?, ?, ?)",
            (offer_name, profile.get("description", "Auto-generated product offer"), price, json.dumps(roles), now)
        )
        offer_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        # Create ResearchCampaign
        conn.execute(
            "INSERT INTO research_campaigns (name, product_id, offer_id, icp_id, status, created_at_utc) VALUES (?, ?, ?, ?, 'DRAFT', ?)",
            (camp_name, product_id, offer_id, icp_id, now)
        )
        campaign_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
    # Generate Query Templates based on Keywords and Markets
    keywords = profile.get("keywords", [])
    top_keywords = keywords[:3] if keywords else [product_name]
    
    # If no markets specified, we generate one set of templates without market suffixes
    target_markets = normalized_markets if normalized_markets else [""]
    
    templates = []
    for kw in top_keywords:
        for market in target_markets:
            market_suffix = f" {market}" if market else ""
            
            # 1. Base Role Query
            templates.append(("PERSON_DISCOVERY", f'{kw} "{{role}}"{market_suffix}'))
            
            # 2. Company Types Query
            if company_types:
                for ct in company_types[:2]: # limit to 2 to avoid explosion
                    templates.append(("COMPANY_DISCOVERY", f'{kw} {ct}{market_suffix}'))
            else:
                templates.append(("COMPANY_DISCOVERY", f'{kw} companies{market_suffix}'))
                templates.append(("COMPANY_DISCOVERY", f'B2B {kw}{market_suffix}'))
                
            # 3. Industry Query
            if industries:
                for ind in industries[:2]:
                    templates.append(("COMPANY_DISCOVERY", f'{kw} {ind}{market_suffix}'))
                    
    for family, text in templates:
        vars_used = []
        if "{role}" in text: vars_used.append("role")
        
        # Check if template already exists
        exists_tmpl = conn.execute(
            "SELECT id FROM query_templates WHERE campaign_id = ? AND template = ?",
            (campaign_id, text)
        ).fetchone()
        
        if not exists_tmpl:
            conn.execute(
                "INSERT INTO query_templates (campaign_id, family, template, variables, enabled, priority, base_score, created_at_utc) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (campaign_id, family, text, json.dumps(vars_used), 1, 0, 50.0, now)
            )
            
    conn.commit()
            
    # Materialize concrete queries deterministically (Idempotent)
    from osint_engine.generator import QueryGenerator
    gen = QueryGenerator(db_path)
    concrete_queries = gen.get_concrete_queries(campaign_id)
    
    # --- P5.2D: QUERY EXPLOSION CONTROL & NEGATIVE KEYWORDS ---
    MAX_QUERIES_PER_CAMPAIGN = 24
    
    # 1. Deduplicate Candidates
    unique_candidates = []
    seen_texts = set()
    for cq in concrete_queries:
        # normalize for deduplication
        norm = " ".join(cq["query"].lower().replace('"', '').split())
        if norm not in seen_texts and norm.strip() and norm != "unknown":
            seen_texts.add(norm)
            unique_candidates.append(cq)
            
    # 2. Negative Keywords Validation
    valid_negatives = []
    for nk in profile.get("negative_keywords", []):
        nk = str(nk).strip()
        if nk and nk.lower() != "unknown" and nk != "-":
            # sanitize alphanumeric
            safe_nk = ''.join(c for c in nk if c.isalnum() or c in " _-")
            if safe_nk:
                # Use standard minus sign syntax supported by almost all search engines
                valid_negatives.append(f"-{safe_nk}")
    
    neg_suffix = (" " + " ".join(valid_negatives)) if valid_negatives else ""
    
    # 3. Scoring & Coverage
    def score_query_candidate(cq_dict):
        score = 100
        text = cq_dict["query"]
        
        # Penalize depth for markets
        for i, market in enumerate(target_markets):
            if market and market in text:
                score -= (i * 10)
                break
                
        # Penalize depth for roles
        for i, role in enumerate(roles):
            if role and role in text:
                score -= (i * 10)
                break
                
        # Penalize depth for keywords
        for i, kw in enumerate(top_keywords):
            if kw and kw in text:
                score -= (i * 5)
                break
                
        # Penalize COMPANY_DISCOVERY slightly to favor PERSON_DISCOVERY
        if cq_dict["family"] == "COMPANY_DISCOVERY":
            score -= 15
            
        return score
        
    for cq in unique_candidates:
        cq["_score"] = score_query_candidate(cq)
        
    # Sort by score descending
    unique_candidates.sort(key=lambda x: x["_score"], reverse=True)
    
    # Ensure Market Coverage
    selected_queries = []
    covered_markets = set()
    covered_roles = set()
    
    # Pass 1: One per market
    for m in target_markets:
        for cq in unique_candidates:
            if m and m in cq["query"] and cq not in selected_queries:
                selected_queries.append(cq)
                covered_markets.add(m)
                break
                
    # Pass 2: One per role (if possible)
    for r in roles:
        if r in covered_roles: continue
        for cq in unique_candidates:
            if r in cq["query"] and cq not in selected_queries:
                selected_queries.append(cq)
                covered_roles.add(r)
                break
                
    # Pass 3: Fill remaining up to cap based on score
    for cq in unique_candidates:
        if len(selected_queries) >= MAX_QUERIES_PER_CAMPAIGN:
            break
        if cq not in selected_queries:
            selected_queries.append(cq)
            
    # Count existing materialized queries to respect cap on incremental updates
    existing_count = conn.execute("SELECT COUNT(*) FROM campaign_queries WHERE campaign_id = ?", (campaign_id,)).fetchone()[0]
    available_budget = max(0, MAX_QUERIES_PER_CAMPAIGN - existing_count)
    
    # 4. Insertion
    inserted_this_run = 0
    for cq in selected_queries:
        if inserted_this_run >= available_budget:
            break
            
        final_query_text = cq["query"] + neg_suffix
            
        exists = conn.execute(
            "SELECT id FROM campaign_queries WHERE campaign_id = ? AND query = ?",
            (campaign_id, final_query_text)
        ).fetchone()
        
        if not exists:
            conn.execute(
                "INSERT INTO campaign_queries (campaign_id, family, query, target_key, is_enabled, status) VALUES (?, ?, ?, ?, 1, 'pending')",
                (campaign_id, cq["family"], final_query_text, cq.get("target_key", ""))
            )
            inserted_this_run += 1
            
    conn.commit()
    conn.close()
    
    return campaign_id
