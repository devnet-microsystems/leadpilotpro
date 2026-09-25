from product_intelligence.sales_strategy_agent import SalesStrategyAgent, EmailSequenceAgent
from product_intelligence.sales_campaign_store import upsert_product_campaign, get_product_campaign
from outreach_sender import OutreachDatabase


def test_sales_strategy_rejects_incomplete_ai_output():
    agent = object.__new__(SalesStrategyAgent)
    result = agent._validate_strategy_payload({"market": "Italy"})
    assert result["status"] == "FAILED"
    assert "core_value_proposition" in result["error"]


def test_email_sequence_rejects_missing_cta():
    agent = object.__new__(EmailSequenceAgent)
    result = agent._validate_and_format_messages(
        [{"subject": "Hello", "body": "Test body", "cta": "", "sequence_order": 1}],
        expected_length=1,
        language="English",
    )
    assert result["status"] == "FAILED"
    assert "CTA" in result["error"]


def test_product_campaign_keeps_strategy_link(tmp_path):
    db_path = tmp_path / "campaign.sqlite3"
    db = OutreachDatabase(db_path)
    db.connection.execute(
        """CREATE TABLE product_sales_strategies (
        id INTEGER PRIMARY KEY, product_id INTEGER, research_campaign_id INTEGER,
        market TEXT, language TEXT, target_segment TEXT, buyer_role TEXT,
        core_value_proposition TEXT, pain_points TEXT, proof_points TEXT,
        primary_cta TEXT, tone TEXT, sequence_strategy TEXT, personalization_fields TEXT,
        provider TEXT, model TEXT, created_at_utc TEXT, updated_at_utc TEXT)"""
    )
    db.connection.execute(
        """CREATE TABLE product_campaigns (
        id INTEGER PRIMARY KEY, name TEXT, product_id INTEGER, research_campaign_id INTEGER,
        strategy_id INTEGER, market TEXT, language TEXT, target_segment TEXT, buyer_role TEXT,
        sequence_length INTEGER, status TEXT, created_at_utc TEXT, updated_at_utc TEXT)"""
    )
    db.connection.execute(
        """CREATE TABLE email_sequence_messages (
        id INTEGER PRIMARY KEY, product_campaign_id INTEGER, sequence_order INTEGER,
        purpose TEXT, language TEXT, subject TEXT, body TEXT, cta TEXT, delay_days INTEGER,
        personalization_fields TEXT, status TEXT, created_at_utc TEXT)"""
    )
    db.connection.execute(
        """INSERT INTO product_sales_strategies (
        id, product_id, market, language, target_segment, buyer_role, core_value_proposition,
        pain_points, proof_points, primary_cta, tone, sequence_strategy, personalization_fields,
        created_at_utc, updated_at_utc) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (7, 1, "Italy", "Italian", "Agencies", "Owner", "Value", "[]", "[]", "Book a call",
         "professional", "sequence", "[]", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
    )
    db.connection.commit()
    db.close()

    campaign_id = upsert_product_campaign(str(db_path), {
        "name": "Test campaign",
        "product_id": 1,
        "research_campaign_id": None,
        "strategy_id": 7,
        "market": "Italy",
        "language": "Italian",
        "target_segment": "Agencies",
        "buyer_role": "Owner",
        "sequence_length": 4,
    })
    campaign = get_product_campaign(str(db_path), campaign_id)
    assert campaign["strategy_id"] == 7