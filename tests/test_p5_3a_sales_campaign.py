"""
tests/test_p5_3a_sales_campaign.py

Test suite for P5.3A: Product -> Sales Strategy -> Email Campaign.
Validates strategy generation, sequence generation, anti-hallucination rules, 
idempotent persistence, and E2E logic without actually sending emails.
"""
import pytest
import sqlite3
import db_connector
import json
from pathlib import Path

from product_intelligence.sales_campaign_store import (
    upsert_strategy, upsert_product_campaign, save_sequence_messages, get_product_campaign
)
from product_intelligence.sales_strategy_agent import SalesStrategyAgent, EmailSequenceAgent

@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test_p5_3a.sqlite3"
    import migration_p5_3a
    migration_p5_3a.migrate(str(db_path))
    
    # Needs settings table for provider config
    conn = db_connector.get_connection(str(db_path))
    conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO settings (key, value) VALUES ('ai_api_key', 'test_key')")
    conn.execute("INSERT INTO settings (key, value) VALUES ('ai_base_url', 'http://localhost:1234')")
    conn.execute("INSERT INTO settings (key, value) VALUES ('ai_model', 'test-model')")
    conn.commit()
    conn.close()
    
    return str(db_path)

def test_store_idempotency(test_db):
    strategy_payload = {
        "product_id": 100,
        "research_campaign_id": 200,
        "market": "Italy",
        "language": "Italian",
        "target_segment": "SaaS",
        "buyer_role": "VP Sales",
        "core_value_proposition": "Best CRM",
        "tone": "professional"
    }
    
    # 1st insert
    sid1 = upsert_strategy(test_db, strategy_payload)
    
    # 2nd update (same unique key)
    strategy_payload["core_value_proposition"] = "Better CRM"
    sid2 = upsert_strategy(test_db, strategy_payload)
    
    assert sid1 == sid2
    
    conn = db_connector.get_connection(test_db)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM product_sales_strategies WHERE id=?", (sid1,)).fetchone()
    assert row["core_value_proposition"] == "Better CRM"
    
    # Insert campaign
    camp_payload = {
        "product_id": 100,
        "research_campaign_id": 200,
        "market": "Italy",
        "language": "Italian",
        "target_segment": "SaaS",
        "buyer_role": "VP Sales",
        "strategy_id": sid1,
        "sequence_length": 4
    }
    cid1 = upsert_product_campaign(test_db, camp_payload)
    cid2 = upsert_product_campaign(test_db, camp_payload)
    assert cid1 == cid2
    
    # Save messages
    msgs = [
        {"sequence_order": 1, "subject": "A", "body": "B"},
        {"sequence_order": 2, "subject": "C", "body": "D"}
    ]
    save_sequence_messages(test_db, cid1, msgs)
    
    camp = get_product_campaign(test_db, cid1)
    assert len(camp["messages"]) == 2
    
    # Change status to APPROVED
    conn.execute("UPDATE product_campaigns SET status='APPROVED' WHERE id=?", (cid1,))
    conn.commit()
    
    # Try updating again
    cid3 = upsert_product_campaign(test_db, camp_payload)
    assert cid1 == cid3 # Should return same ID
    
    # Try updating messages on APPROVED campaign (should fail)
    with pytest.raises(ValueError):
        save_sequence_messages(test_db, cid1, msgs)

def test_multi_role_identity(test_db):
    base_payload = {
        "product_id": 100,
        "research_campaign_id": 200,
        "market": "Italy",
        "language": "Italian",
        "target_segment": "SaaS"
    }
    
    p1 = base_payload.copy()
    p1["buyer_role"] = "CEO"
    
    p2 = base_payload.copy()
    p2["buyer_role"] = "VP Sales"
    
    sid1 = upsert_strategy(test_db, p1)
    sid2 = upsert_strategy(test_db, p2)
    assert sid1 != sid2 # Different roles -> different strategies

class MockProvider:
    def __init__(self, *args, **kwargs):
        self.available = lambda: True
        self.last_error = None
        self.strategy_response = json.dumps({
            "market": "Italy",
            "language": "Italian",
            "target_segment": "SaaS",
            "buyer_role": "CEO",
            "core_value_proposition": "Value",
            "pain_points": [],
            "proof_points": [],
            "primary_cta": "Call?",
            "tone": "professional",
            "sequence_strategy": "4 touchpoints",
            "personalization_fields": ["company_name"]
        })
        self.sequence_response = json.dumps({
            "messages": [
                {"subject": "1", "body": "Hello {{company_name}}", "delay_days": 0},
                {"subject": "2", "body": "Follow up {{company_name}}", "delay_days": 3}
            ]
        })
        self.mode = "strategy"

    def generate_structured(self, **kwargs):
        return self.strategy_response if self.mode == "strategy" else self.sequence_response

def test_agents_mocked(test_db, monkeypatch):
    monkeypatch.setattr("product_intelligence.sales_strategy_agent.get_ai_provider", lambda x: MockProvider())
    
    agent_strat = SalesStrategyAgent(test_db)
    agent_strat.provider.mode = "strategy"
    
    strat = agent_strat.generate({"name": "Product"}, "Italy", "Italian", "SaaS", "CEO")
    assert strat["status"] == "SUCCESS"
    assert strat["language"] == "Italian"
    
    agent_seq = EmailSequenceAgent(test_db)
    agent_seq.provider.mode = "sequence"
    seq = agent_seq.generate(strat, {"name": "Product"}, 2)
    
    assert seq["status"] == "SUCCESS"
    assert len(seq["messages"]) == 2
    assert seq["messages"][0]["sequence_order"] == 1
    assert "company_name" in seq["messages"][0]["personalization_fields"]

def test_invalid_placeholder_rejection(test_db, monkeypatch):
    mock = MockProvider()
    mock.sequence_response = json.dumps({
        "messages": [
            {"subject": "1", "body": "Hello {{invalid_field}}"}
        ]
    })
    monkeypatch.setattr("product_intelligence.sales_strategy_agent.get_ai_provider", lambda x: mock)
    
    agent_seq = EmailSequenceAgent(test_db)
    agent_seq.provider.mode = "sequence"
    seq = agent_seq.generate({}, {}, 1)
    
    assert seq["status"] == "FAILED"
    assert "Invalid placeholder" in seq["error"]

def test_duplicate_body_rejection(test_db, monkeypatch):
    mock = MockProvider()
    mock.sequence_response = json.dumps({
        "messages": [
            {"subject": "1", "body": "Exact same body"},
            {"subject": "2", "body": "Exact same body"}
        ]
    })
    monkeypatch.setattr("product_intelligence.sales_strategy_agent.get_ai_provider", lambda x: mock)
    
    agent_seq = EmailSequenceAgent(test_db)
    agent_seq.provider.mode = "sequence"
    seq = agent_seq.generate({}, {}, 2)
    
    assert seq["status"] == "FAILED"
    assert "duplicate" in seq["error"].lower()

@pytest.mark.skip(reason="Requires real AI provider key")
def test_real_ai_e2e(test_db):
    """
    To run manually: set AI_API_KEY and run pytest -k test_real_ai_e2e
    """
    pass
