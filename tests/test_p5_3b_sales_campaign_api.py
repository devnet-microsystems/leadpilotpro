import pytest
from fastapi.testclient import TestClient
import sqlite3
import db_connector
import json

from web_server import app, DB_PATH, get_current_user
from product_intelligence.provider import get_ai_provider

app.dependency_overrides[get_current_user] = lambda: {"username": "admin"}
client = TestClient(app)

@pytest.fixture
def test_db(fresh_db):
    """DB isolato con schema completo (vedi conftest.fresh_db). Non copia piu' il DB di produzione."""
    return fresh_db

def setup_mock_data(db_path):
    conn = db_connector.get_connection(db_path)
    
    # 1. Product
    conn.execute("INSERT INTO products (id, name, slug, status, raw_summary, created_at_utc, updated_at_utc) VALUES (10, 'Test CRM', 'test-crm', 'READY', '{\"pricing_information\": {\"status\":\"UNKNOWN\"}}', 'now', 'now')")
    
    # 2. ICP
    icp_countries = json.dumps(["Italy", "Spain"])
    icp_langs = json.dumps(["Italian", "Spanish"])
    icp_inds = json.dumps(["SaaS", "Fintech"])
    icp_roles = json.dumps(["CEO", "CTO"])
    conn.execute("INSERT INTO ideal_customer_profiles (id, name, roles, industries, company_sizes, countries, languages, created_at_utc) VALUES (20, 'ICP 1', ?, ?, 'Any', ?, ?, 'now')",
                 (icp_roles, icp_inds, icp_countries, icp_langs))
                 
    # 3. Research Campaign
    conn.execute("INSERT INTO research_campaigns (id, name, icp_id, product_id, created_at_utc) VALUES (30, 'Camp 1', 20, 10, 'now')")
    # Another campaign for a different product
    conn.execute("INSERT INTO products (id, name, slug, status, created_at_utc, updated_at_utc) VALUES (11, 'Other CRM', 'other-crm', 'READY', 'now', 'now')")
    conn.execute("INSERT INTO research_campaigns (id, name, icp_id, product_id, created_at_utc) VALUES (31, 'Camp 2', 20, 11, 'now')")
    
    conn.execute("INSERT INTO prospects (id, company_name, business_email, target_url, source_file, imported_at_utc, status) VALUES (999, 'A', 'a@a.com', 'x', 'x', 'now', 'pending_review')")
    conn.execute("INSERT INTO prospect_product_fit (prospect_id, product_id, fit_status, evidence_reviewed_at) VALUES (999, 10, 'FIT', 'now')")
    
    conn.commit()
    conn.close()

def test_get_research_campaigns_filter(test_db):
    setup_mock_data(test_db)
    # Get all
    res = client.get("/api/research_campaigns")
    assert res.status_code == 200
    assert len(res.json()) == 2
    
    # Filter by product_id
    res = client.get("/api/research_campaigns?product_id=10")
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["id"] == 30

def test_get_contexts(test_db):
    setup_mock_data(test_db)
    conn = db_connector.get_connection(test_db)
    conn.execute("INSERT INTO campaign_queries (campaign_id, family, query, target_key, is_enabled) VALUES (30, 'DISCOVERY', 'query1', 'CEO|SaaS|Italy', 1)")
    conn.execute("INSERT INTO campaign_queries (campaign_id, family, query, target_key, is_enabled) VALUES (30, 'DISCOVERY', 'query2', 'CTO|Fintech|Spain', 1)")
    conn.commit()
    conn.close()
    
    res = client.get("/api/research_campaigns/30/contexts")
    assert res.status_code == 200
    data = res.json()
    assert data["product_id"] == 10
    contexts = data["contexts"]
    assert len(contexts) == 4 # 2 target keys * 2 languages (Italian, Spanish)
    
    # Check one of the expected combinations
    expected = {"buyer_role": "CEO", "target_segment": "SaaS", "market": "Italy", "language": "Italian"}
    assert expected in contexts

class MockProvider:
    def __init__(self, *args, **kwargs):
        self.available = lambda: True
        self.last_error = None
        self.model_name = "mock"
        self.provider_name = "mock"
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
            "sequence_strategy": "4 touches",
            "personalization_fields": ["company_name"]
        })
        self.sequence_response = json.dumps({
            "messages": [
                {"sequence_order": 1, "subject": "S1", "body": "B1 {{company_name}}", "delay_days": 0},
                {"sequence_order": 2, "subject": "S2", "body": "B2", "delay_days": 3},
                {"sequence_order": 3, "subject": "S3", "body": "B3", "delay_days": 7},
                {"sequence_order": 4, "subject": "S4", "body": "B4", "delay_days": 12}
            ]
        })

    def generate_structured(self, system_prompt, **kwargs):
        if "Sales Strategy Expert" in system_prompt:
            return self.strategy_response
        return self.sequence_response

def test_strategy_generate_api(test_db, monkeypatch):
    setup_mock_data(test_db)
    monkeypatch.setattr("web_server.SalesStrategyAgent.generate", lambda self, product_profile, market, language, target_segment, buyer_role: json.loads(MockProvider().strategy_response) | {"status": "SUCCESS"})
    
    # Test mismatch rejection
    res = client.post("/api/sales_strategy/generate", json={
        "product_id": 10,
        "research_campaign_id": 31, # belongs to 11
        "market": "Italy",
        "language": "Italian",
        "target_segment": "SaaS",
        "buyer_role": "CEO"
    })
    assert res.status_code == 400
    
    # Test success
    res = client.post("/api/sales_strategy/generate", json={
        "product_id": 10,
        "research_campaign_id": 30,
        "market": "Italy",
        "language": "Italian",
        "target_segment": "SaaS",
        "buyer_role": "CEO"
    })
    assert res.status_code == 200
    assert res.json()["success"] == True
    sid = res.json()["strategy_id"]
    
    # Retrieve it
    res = client.get("/api/sales_strategy?product_id=10&research_campaign_id=30&market=Italy&language=Italian&target_segment=SaaS&buyer_role=CEO")
    assert res.status_code == 200
    assert res.json()["id"] == sid

def test_campaign_generate_api(test_db, monkeypatch):
    setup_mock_data(test_db)
    # Generate strategy first
    monkeypatch.setattr("web_server.SalesStrategyAgent.generate", lambda self, product_profile, market, language, target_segment, buyer_role: json.loads(MockProvider().strategy_response) | {"status": "SUCCESS"})
    client.post("/api/sales_strategy/generate", json={
        "product_id": 10, "research_campaign_id": 30, "market": "Italy", "language": "Italian", "target_segment": "SaaS", "buyer_role": "CEO"
    })
    
    monkeypatch.setattr("web_server.EmailSequenceAgent.generate", lambda self, strat, profile, length: json.loads(MockProvider().sequence_response) | {"status": "SUCCESS"})
    
    # Generate Campaign
    res = client.post("/api/product_campaigns/generate", json={
        "product_id": 10,
        "research_campaign_id": 30,
        "market": "Italy",
        "language": "Italian",
        "target_segment": "SaaS",
        "buyer_role": "CEO",
        "sequence_length": 4
    })
    assert res.status_code == 200
    cid = res.json()["campaign_id"]
    
    # Fetch campaign
    res = client.get(f"/api/product_campaigns/{cid}")
    assert res.status_code == 200
    camp = res.json()
    assert camp["status"] == "DRAFT"
    assert len(camp["messages"]) == 4

def test_campaign_edit_and_approve(test_db, monkeypatch):
    setup_mock_data(test_db)
    monkeypatch.setattr("web_server.SalesStrategyAgent.generate", lambda self, product_profile, market, language, target_segment, buyer_role: json.loads(MockProvider().strategy_response) | {"status": "SUCCESS"})
    client.post("/api/sales_strategy/generate", json={"product_id": 10, "research_campaign_id": 30, "market": "Italy", "language": "Italian", "target_segment": "SaaS", "buyer_role": "CEO"})
    monkeypatch.setattr("web_server.EmailSequenceAgent.generate", lambda self, strat, profile, length: json.loads(MockProvider().sequence_response) | {"status": "SUCCESS"})
    res = client.post("/api/product_campaigns/generate", json={"product_id": 10, "research_campaign_id": 30, "market": "Italy", "language": "Italian", "target_segment": "SaaS", "buyer_role": "CEO", "sequence_length": 4})
    cid = res.json()["campaign_id"]
    
    # Edit message
    msgs = client.get(f"/api/product_campaigns/{cid}").json()["messages"]
    msgs[0]["subject"] = "New Subject"
    
    res = client.put(f"/api/product_campaigns/{cid}/messages", json={"messages": msgs})
    assert res.status_code == 200
    
    msgs = client.get(f"/api/product_campaigns/{cid}").json()["messages"]
    assert msgs[0]["subject"] == "New Subject"
    
    # Try invalid placeholder
    msgs[0]["body"] = "Hello {{invalid}}"
    res = client.put(f"/api/product_campaigns/{cid}/messages", json={"messages": msgs})
    assert res.status_code == 400
    assert "Invalid placeholder" in res.json()["detail"]
    
    msgs[0]["body"] = "Valid {{company_name}}"
    res = client.put(f"/api/product_campaigns/{cid}/messages", json={"messages": msgs})
    
    # Approve
    res = client.post(f"/api/product_campaigns/{cid}/approve")
    if res.status_code != 200:
        print("APPROVE ERROR:", res.text)
    assert res.status_code == 200
    assert res.json()["status"] == "APPROVED"
    
    # Check status
    camp = client.get(f"/api/product_campaigns/{cid}").json()
    assert camp["status"] == "APPROVED"
    
    # Editing should now fail
    res = client.put(f"/api/product_campaigns/{cid}/messages", json={"messages": msgs})
    assert res.status_code == 400
    assert "Cannot edit" in res.json()["detail"]
