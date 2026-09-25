"""
product_intelligence/sales_campaign_store.py

Persistence layer for product-driven sales campaigns, strategies, and sequences.
Operates on:
- product_sales_strategies
- product_campaigns
- email_sequence_messages
"""
import sqlite3
import db_connector
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def upsert_strategy(db_path: str, strategy: Dict[str, Any]) -> int:
    """
    Idempotent insert or update of a sales strategy.
    Unique identity: (product_id, research_campaign_id, market, language, target_segment, buyer_role).
    Returns the strategy_id.
    """
    conn = db_connector.get_connection(db_path)
    conn.row_factory = sqlite3.Row
    try:
        pid = strategy["product_id"]
        rcid = strategy.get("research_campaign_id")
        market = strategy.get("market", "")
        language = strategy.get("language", "English")
        target_segment = strategy.get("target_segment", "")
        buyer_role = strategy.get("buyer_role", "")
        
        now = _utc_now()
        
        # Check if exists
        existing = conn.execute("""
            SELECT id FROM product_sales_strategies
            WHERE product_id=? AND (research_campaign_id=? OR (? IS NULL AND research_campaign_id IS NULL))
              AND market=? AND language=? AND target_segment=? AND buyer_role=?
        """, (pid, rcid, rcid, market, language, target_segment, buyer_role)).fetchone()
        
        pain_points = json.dumps(strategy.get("pain_points", []))
        proof_points = json.dumps(strategy.get("proof_points", []))
        pers_fields = json.dumps(strategy.get("personalization_fields", []))
        
        if existing:
            strategy_id = existing["id"]
            conn.execute("""
                UPDATE product_sales_strategies SET
                    core_value_proposition=?,
                    pain_points=?,
                    proof_points=?,
                    primary_cta=?,
                    tone=?,
                    sequence_strategy=?,
                    personalization_fields=?,
                    provider=?,
                    model=?,
                    updated_at_utc=?
                WHERE id=?
            """, (
                strategy.get("core_value_proposition"),
                pain_points,
                proof_points,
                strategy.get("primary_cta"),
                strategy.get("tone", "professional"),
                strategy.get("sequence_strategy"),
                pers_fields,
                strategy.get("provider"),
                strategy.get("model"),
                now,
                strategy_id
            ))
        else:
            cur = conn.execute("""
                INSERT INTO product_sales_strategies (
                    product_id, research_campaign_id, market, language, target_segment, buyer_role,
                    core_value_proposition, pain_points, proof_points, primary_cta, tone,
                    sequence_strategy, personalization_fields, provider, model,
                    created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pid, rcid, market, language, target_segment, buyer_role,
                strategy.get("core_value_proposition"), pain_points, proof_points,
                strategy.get("primary_cta"), strategy.get("tone", "professional"),
                strategy.get("sequence_strategy"), pers_fields,
                strategy.get("provider"), strategy.get("model"),
                now, now
            ))
            strategy_id = cur.lastrowid
            
        conn.commit()
        return strategy_id
    finally:
        conn.close()

def upsert_product_campaign(db_path: str, campaign: Dict[str, Any]) -> int:
    """
    Idempotent insert or update of a product campaign container.
    If the campaign exists and its status is NOT 'DRAFT', it is not overwritten, 
    and the existing ID is returned without modifications.
    """
    conn = db_connector.get_connection(db_path)
    conn.row_factory = sqlite3.Row
    try:
        pid = campaign["product_id"]
        rcid = campaign.get("research_campaign_id")
        market = campaign.get("market", "")
        language = campaign.get("language", "English")
        target_segment = campaign.get("target_segment", "")
        buyer_role = campaign.get("buyer_role", "")
        
        now = _utc_now()
        
        existing = conn.execute("""
            SELECT id, status FROM product_campaigns
            WHERE product_id=? AND (research_campaign_id=? OR (? IS NULL AND research_campaign_id IS NULL))
              AND market=? AND language=? AND target_segment=? AND buyer_role=?
        """, (pid, rcid, rcid, market, language, target_segment, buyer_role)).fetchone()
        
        if existing:
            campaign_id = existing["id"]
            if existing["status"] != 'DRAFT':
                # Preserve non-DRAFT campaigns (e.g. APPROVED, ACTIVE, SENT)
                return campaign_id
                
            conn.execute("""
                UPDATE product_campaigns SET
                    strategy_id=?,
                    sequence_length=?,
                    updated_at_utc=?
                WHERE id=?
            """, (
                campaign.get("strategy_id"),
                campaign.get("sequence_length", 4),
                now,
                campaign_id
            ))
        else:
            name = campaign.get("name", f"Campaign: {target_segment} - {buyer_role} ({market})")
            cur = conn.execute("""
                INSERT INTO product_campaigns (
                    name, product_id, research_campaign_id, strategy_id,
                    market, language, target_segment, buyer_role,
                    sequence_length, status, created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?)
            """, (
                name, pid, rcid, campaign.get("strategy_id"),
                market, language, target_segment, buyer_role,
                campaign.get("sequence_length", 4),
                now, now
            ))
            campaign_id = cur.lastrowid
            
        conn.commit()
        return campaign_id
    finally:
        conn.close()

def save_sequence_messages(db_path: str, campaign_id: int, messages: List[Dict[str, Any]]) -> None:
    """
    Saves a sequence of emails for a campaign.
    Requires the campaign to be in DRAFT status. Replaces existing DRAFT messages for this campaign.
    """
    conn = db_connector.get_connection(db_path)
    conn.row_factory = sqlite3.Row
    try:
        camp = conn.execute("SELECT status FROM product_campaigns WHERE id=?", (campaign_id,)).fetchone()
        if not camp:
            raise ValueError(f"Campaign {campaign_id} not found.")
        if camp["status"] != 'DRAFT':
            raise ValueError(f"Cannot update messages for campaign {campaign_id} with status {camp['status']}")
            
        # Delete existing messages
        conn.execute("DELETE FROM email_sequence_messages WHERE product_campaign_id=?", (campaign_id,))
        
        now = _utc_now()
        for msg in messages:
            pers_fields = json.dumps(msg.get("personalization_fields", []))
            conn.execute("""
                INSERT INTO email_sequence_messages (
                    product_campaign_id, sequence_order, purpose, language,
                    subject, body, cta, delay_days, personalization_fields,
                    status, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?)
            """, (
                campaign_id,
                msg.get("sequence_order", 1),
                msg.get("purpose", ""),
                msg.get("language", "English"),
                msg.get("subject", ""),
                msg.get("body", ""),
                msg.get("cta"),
                msg.get("delay_days", 0),
                pers_fields,
                now
            ))
            
        conn.commit()
    finally:
        conn.close()

def get_product_campaign(db_path: str, campaign_id: int) -> Optional[Dict[str, Any]]:
    """
    Returns the campaign with its strategy and messages.
    """
    conn = db_connector.get_connection(db_path)
    conn.row_factory = sqlite3.Row
    try:
        camp = conn.execute("SELECT * FROM product_campaigns WHERE id=?", (campaign_id,)).fetchone()
        if not camp:
            return None
            
        result = dict(camp)
        
        # Get strategy if present
        if result.get("strategy_id"):
            strat = conn.execute("SELECT * FROM product_sales_strategies WHERE id=?", (result["strategy_id"],)).fetchone()
            if strat:
                s_dict = dict(strat)
                # Parse JSON fields
                for k in ["pain_points", "proof_points", "personalization_fields"]:
                    if s_dict.get(k):
                        s_dict[k] = json.loads(s_dict[k])
                result["strategy"] = s_dict
                
        # Get messages
        msgs = conn.execute("SELECT * FROM email_sequence_messages WHERE product_campaign_id=? ORDER BY sequence_order ASC", (campaign_id,)).fetchall()
        messages = []
        for m in msgs:
            m_dict = dict(m)
            if m_dict.get("personalization_fields"):
                m_dict["personalization_fields"] = json.loads(m_dict["personalization_fields"])
            messages.append(m_dict)
            
        result["messages"] = messages
        return result
    finally:
        conn.close()

def list_product_campaigns(db_path: str, product_id: int) -> List[Dict[str, Any]]:
    """
    Lists all product campaigns for a given product.
    """
    conn = db_connector.get_connection(db_path)
    conn.row_factory = sqlite3.Row
    try:
        camps = conn.execute("SELECT * FROM product_campaigns WHERE product_id=? ORDER BY created_at_utc DESC", (product_id,)).fetchall()
        return [dict(c) for c in camps]
    finally:
        conn.close()

def get_strategy_by_identity(db_path: str, product_id: int, research_campaign_id: int, market: str, language: str, target_segment: str, buyer_role: str) -> Optional[Dict[str, Any]]:
    conn = db_connector.get_connection(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("""
            SELECT * FROM product_sales_strategies 
            WHERE product_id=? AND research_campaign_id=? AND market=? AND language=? AND target_segment=? AND buyer_role=?
        """, (product_id, research_campaign_id, market, language, target_segment, buyer_role)).fetchone()
        
        if not row:
            return None
            
        res = dict(row)
        res["pain_points"] = json.loads(res["pain_points"]) if res["pain_points"] else []
        res["proof_points"] = json.loads(res["proof_points"]) if res["proof_points"] else []
        return res
    finally:
        conn.close()
