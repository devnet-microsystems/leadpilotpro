"""
Test di finalizzazione (P6): copre i difetti trovati nell'audit del 21/09/2026.

Tutti usano DB temporanei e SMTP disabilitato (vedi conftest.py).
"""
import json
import sqlite3
import db_connector
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import outreach_sender
from email_hygiene import junk_reason
from outreach_sender import OutreachDatabase, MailSettings, build_message, read_template, send_message, SmtpDisabledError
from product_intelligence import outreach_bridge
from product_intelligence.sales_strategy_agent import EmailSequenceAgent
from web_server import app, get_current_user

app.dependency_overrides[get_current_user] = lambda: {"username": "admin"}
client = TestClient(app)


# ─────────────────────────────────────────────────────────────── igiene email

@pytest.mark.parametrize("email,expected", [
    ("0613d19f7d0cef15a2955a080ef101bb@sentry.matchtv.ru", "error_tracking_key"),
    ("fdfb6bf0d26e476ca81a568ea5291234@o408587.ingest.sentry.io", "error_tracking_key"),
    ("325506e3332d487999567a7bc91d151d@bug-reporting-xalgh.merriam-webster.com", "error_tracking_key"),
    ("jane@example.com", "reserved_domain"),
    ("someone@foo.test", "reserved_domain"),
    ("votre@email.com", "placeholder_domain"),
    ("vous@exemple.com", "placeholder_domain"),
    ("info@musterfirma.de", "placeholder_domain"),
    ("logo@2x.png", "file_extension"),
    ("noreply@acme.io", "system_mailbox"),
    ("ceo_1789853271@legacy.com", "test_fixture_address"),
    ("user0_1789831111.265068@dedup.com", "test_fixture_address"),
    ("not-an-email", "invalid_syntax"),
    ("", "invalid_syntax"),
    (None, "invalid_syntax"),
])
def test_junk_addresses_are_recognised(email, expected):
    assert junk_reason(email) == expected


@pytest.mark.parametrize("email", [
    "info@carholmedentalgroup.co.uk", "sales@rnstechnology.com", "hello@mastt.com",
    "info@pixelwerker.de", "support@stripe.com", "info@musterhaus.de", "ceo@legacy.com",
])
def test_legitimate_addresses_are_not_blocked(email):
    assert junk_reason(email) is None


def test_osint_email_validator_rejects_junk():
    from osint_engine.quality import EmailValidator
    assert EmailValidator.classify("0a006695b9724da380146d45dc995cde@sentry.io", 0.95, "SYSTEM") == "INVALID"
    assert EmailValidator.classify("you@example.com", 0.95, "PERSONAL") == "INVALID"
    assert EmailValidator.classify("info@pixelwerker.de", 0.95, "ROLE_BASED") == "ROLE_BASED"


# ─────────────────────────────────────────────────────────────── sender

def _add_prospect(db_path, email, status="approved", campaign="c1"):
    db = OutreachDatabase(Path(db_path))
    cid = db.get_or_create_campaign_id(campaign)
    db.connection.execute(
        """INSERT INTO prospects (target_url, company_name, business_email, source_file, campaign_id, status,
                                  reason_for_contact, imported_at_utc, approved_at_utc, qualification_status)
           VALUES ('https://x.io', 'X', ?, 'test', ?, ?, 'why', '2026-01-01', '2026-01-02', 'QUALIFIED')""",
        (email, cid, status))
    db.connection.close()


def test_sender_never_selects_junk_and_rejects_it(fresh_db):
    _add_prospect(fresh_db, "0613d19f7d0cef15a2955a080ef101bb@sentry.io")
    _add_prospect(fresh_db, "founder_1789853271@legacy.com")
    _add_prospect(fresh_db, "hello@realagency.io")

    db = OutreachDatabase(Path(fresh_db))
    rows = db.approved_for_campaign("c1", 10)
    assert [r["business_email"] for r in rows] == ["hello@realagency.io"]

    statuses = dict(db.connection.execute("SELECT business_email, status FROM prospects").fetchall())
    assert statuses["0613d19f7d0cef15a2955a080ef101bb@sentry.io"] == "rejected"
    assert statuses["founder_1789853271@legacy.com"] == "rejected"
    reason = db.connection.execute(
        "SELECT rejection_reason FROM prospects WHERE business_email LIKE '%sentry.io'").fetchone()[0]
    assert reason == "error_tracking_key"


def test_junk_does_not_crowd_out_valid_prospects_within_the_limit(fresh_db):
    for i in range(3):
        _add_prospect(fresh_db, f"{i:032x}@sentry.io")
    _add_prospect(fresh_db, "hello@realagency.io")
    db = OutreachDatabase(Path(fresh_db))
    assert len(db.approved_for_campaign("c1", 1)) == 1  # limit=1, ma i 3 junk davanti non lo occupano


def test_approve_rejects_junk_instead_of_approving(fresh_db):
    _add_prospect(fresh_db, "jane@example.com", status="pending_review")
    _add_prospect(fresh_db, "hello@realagency.io", status="pending_review")
    ids = {e: i for i, e in OutreachDatabase(Path(fresh_db)).connection.execute(
        "SELECT id, business_email FROM prospects").fetchall()}
    res = client.post("/api/approve_selected", json={"ids": list(ids.values()), "campaign": "c1"})
    assert res.status_code == 200
    assert res.json()["count"] == 1 and res.json()["rejected_junk"] == 1


def test_smtp_is_disabled_under_test(fresh_db):
    settings = MailSettings("smtp.invalid", 587, "u", "p", "N", "a@b.io", "a@b.io", "a@b.io", "Co", "https://b.io", 5, 1, 2)
    msg = build_message({"business_email": "x@y.io", "company_name": "Y", "target_url": "https://y.io",
                         "reason_for_contact": "r"}, settings, "Subject: hi\n\nbody")
    with pytest.raises(SmtpDisabledError):
        send_message(msg, settings)


# ─────────────────────────────────────────────────────────────── agente sequenze

class _SeqProvider:
    def __init__(self, messages):
        self._raw = json.dumps({"messages": messages})
        self.last_error = None

    def available(self):
        return True

    def generate_structured(self, **kwargs):
        return self._raw


def _msgs(n, **extra):
    return [{"subject": f"S{i}", "body": f"Body number {i} for {{{{company_name}}}}", **extra} for i in range(1, n + 1)]


def _agent(monkeypatch, messages):
    monkeypatch.setattr("product_intelligence.sales_strategy_agent.get_ai_provider", lambda db: _SeqProvider(messages))
    return EmailSequenceAgent("unused.sqlite3")


def test_agent_fails_when_ai_returns_too_few_emails(monkeypatch):
    res = _agent(monkeypatch, _msgs(3)).generate({"language": "English"}, {}, 4)
    assert res["status"] == "FAILED" and "3 of 4" in res["error"]


def test_agent_truncates_extra_emails(monkeypatch):
    res = _agent(monkeypatch, _msgs(6)).generate({"language": "English"}, {}, 4)
    assert res["status"] == "SUCCESS" and len(res["messages"]) == 4


def test_agent_normalises_delay_days(monkeypatch):
    msgs = _msgs(3)
    msgs[0]["delay_days"] = "0"
    msgs[1]["delay_days"] = "3 days"
    msgs[2]["delay_days"] = None
    res = _agent(monkeypatch, msgs).generate({"language": "English"}, {}, 3)
    assert [m["delay_days"] for m in res["messages"]] == [0, 3, 7]


# ─────────────────────────────────────────────────────────────── ponte verso Outreach

def test_converted_template_is_valid_for_the_legacy_sender(tmp_path):
    content, dropped = outreach_bridge.build_legacy_template(
        "Question for {{first_name}}",
        "Hi {{first_name}} {{last_name}},\n\nSaw {{why_matched}} at {{company_name}}. Config {\"a\": 1}.\n\nBest",
        "Italian")
    assert dropped == {"last_name"}
    f = tmp_path / "t.txt"
    f.write_text(content, encoding="utf-8")
    subject, body = read_template(f)            # stessa validazione del sender vero
    assert "{first_name}" not in subject and "{{" not in body.replace("{{\"a\"", "")

    settings = MailSettings("h", 587, "u", "p", "Antonio", "a@dev.io", "a@dev.io", "unsub@dev.io", "DevCo", "https://dev.io", 5, 1, 2)
    msg = build_message({"business_email": "info@acme.io", "company_name": "Acme", "target_url": "https://acme.io",
                         "reason_for_contact": "your public API docs"}, settings, content)
    text = msg.get_content()
    assert "Acme" in text and "your public API docs" in text and '{"a": 1}' in text
    assert "unsub@dev.io" in text and "DevCo" in text     # footer di opt-out compilato


def test_converter_rejects_unknown_placeholder():
    with pytest.raises(ValueError):
        outreach_bridge.build_legacy_template("s", "Hello {{nope}}")


# ─────────────────────────────────────────────────────────────── flusso completo via API

STRATEGY = {"market": "Italy", "language": "Italian", "target_segment": "SaaS", "buyer_role": "CEO",
            "core_value_proposition": "Value", "pain_points": ["p1"], "proof_points": [], "primary_cta": "Call?",
            "tone": "professional", "sequence_strategy": "4 touches", "personalization_fields": ["company_name"]}
CTX = {"product_id": 10, "research_campaign_id": 30, "market": "Italy", "language": "Italian",
       "target_segment": "SaaS", "buyer_role": "CEO"}


def _seed(db_path):
    conn = db_connector.get_connection(db_path)
    conn.execute("INSERT INTO products (id, name, slug, status, raw_summary, created_at_utc, updated_at_utc) "
                 "VALUES (10, 'CRM', 'crm', 'READY', '{\"name\": \"CRM\"}', 'now', 'now')")
    conn.execute("INSERT INTO ideal_customer_profiles (id, name, roles, industries, company_sizes, countries, languages, created_at_utc) "
                 "VALUES (20, 'ICP', ?, ?, 'Any', ?, ?, 'now')",
                 (json.dumps(["CEO", "CTO"]), json.dumps(["SaaS"]), json.dumps(["Italy"]), json.dumps(["Italian"])))
    conn.execute("INSERT INTO research_campaigns (id, name, icp_id, product_id, created_at_utc) VALUES (30, 'RC', 20, 10, 'now')")
    # Insert concrete queries so Context Discovery API has real targets to return
    conn.execute("INSERT INTO campaign_queries (campaign_id, family, query, target_key, is_enabled) VALUES (30, 'DISCOVERY', 'query1', 'CEO|SaaS|Italy', 1)")
    conn.execute("INSERT INTO campaign_queries (campaign_id, family, query, target_key, is_enabled) VALUES (30, 'DISCOVERY', 'query2', 'CTO|SaaS|Italy', 1)")
    conn.execute("INSERT INTO prospects (id, company_name, business_email, target_url, source_file, imported_at_utc, status) VALUES (999, 'A', 'a@a.com', 'x', 'x', 'now', 'pending_review')")
    conn.execute("INSERT INTO prospect_product_fit (prospect_id, product_id, fit_status, evidence_reviewed_at) VALUES (999, 10, 'FIT', 'now')")
    conn.commit()
    conn.close()


def _mock_agents(monkeypatch, sequence):
    monkeypatch.setattr("web_server.SalesStrategyAgent.generate",
                        lambda self, product_profile, market, language, target_segment, buyer_role: {**STRATEGY, "status": "SUCCESS"})
    monkeypatch.setattr("web_server.EmailSequenceAgent.generate",
                        lambda self, strat, profile, length: {"status": "SUCCESS", "messages": sequence})


def _sequence():
    return [
        {"sequence_order": 1, "subject": "S1 {{ company_name }}", "body": "B1 {{first_name}} {{why_matched}}", "delay_days": 0},
        {"sequence_order": 2, "subject": "S2", "body": "B2", "delay_days": 3},
        {"sequence_order": 3, "subject": "S3", "body": "B3 {{role}}", "delay_days": 7},
        {"sequence_order": 4, "subject": "S4", "body": "B4", "delay_days": 12},
    ]


def test_full_flow_generate_edit_approve_export(fresh_db, monkeypatch):
    _seed(fresh_db)
    _mock_agents(monkeypatch, _sequence())

    # Update test to reflect new P5.3B Context Discovery contract (No Cartesian Product)
    ctx_res = client.get("/api/research_campaigns/30/contexts").json()
    assert "contexts" in ctx_res
    contexts = ctx_res["contexts"]
    assert len(contexts) == 2, f"Expected 2 contexts, got {len(contexts)}"
    assert any(c["buyer_role"] == "CEO" and c["target_segment"] == "SaaS" and c["market"] == "Italy" and c["language"] == "Italian" for c in contexts)
    assert any(c["buyer_role"] == "CTO" and c["target_segment"] == "SaaS" and c["market"] == "Italy" and c["language"] == "Italian" for c in contexts)
    
    r = client.post("/api/sales_strategy/generate", json=CTX)
    assert r.status_code == 200 and r.json()["strategy"]["core_value_proposition"] == "Value"

    assert client.get("/api/product_campaign_lookup", params=CTX).json()["campaign_id"] is None
    cid = client.post("/api/product_campaigns/generate", json={**CTX, "sequence_length": 4}).json()["campaign_id"]
    assert client.get("/api/product_campaign_lookup", params=CTX).json()["campaign_id"] == cid

    # export prima dell'approvazione: vietato
    assert client.post(f"/api/product_campaigns/{cid}/export_to_outreach").status_code == 400

    msgs = client.get(f"/api/product_campaigns/{cid}").json()["messages"]
    assert client.put(f"/api/product_campaigns/{cid}/messages", json={"messages": msgs}).status_code == 200  # {{ company_name }} con spazi
    msgs[1]["subject"] = "Bad {{ nope }}"
    bad = client.put(f"/api/product_campaigns/{cid}/messages", json={"messages": msgs})
    assert bad.status_code == 400 and "Invalid placeholder" in bad.json()["detail"]      # controllato anche l'oggetto
    msgs[1]["subject"] = "S2"

    assert client.post(f"/api/product_campaigns/{cid}/approve").status_code == 200

    # rigenerare una campagna APPROVED: saltato, l'AI non viene nemmeno chiamata
    monkeypatch.setattr("web_server.EmailSequenceAgent.generate",
                        lambda *a, **k: pytest.fail("AI must not be called for a non-DRAFT campaign"))
    again = client.post("/api/product_campaigns/generate", json={**CTX, "sequence_length": 4}).json()
    assert again["skipped"] is True and again["status"] == "APPROVED" and again["campaign_id"] == cid

    exp = client.post(f"/api/product_campaigns/{cid}/export_to_outreach")
    assert exp.status_code == 200
    body = exp.json()
    assert len(body["created"]) == 4 and body["existing"] == [] and body["warnings"]  # 'role' senza dati -> avviso

    conn = db_connector.get_connection(fresh_db)
    assert conn.execute("SELECT COUNT(*) FROM templates").fetchone()[0] == 4
    assert conn.execute("SELECT COUNT(*) FROM campaigns WHERE name LIKE 'PC%'").fetchone()[0] == 4
    # ogni template esportato e' accettato dal sender vero
    for (content,) in conn.execute("SELECT content FROM templates"):
        p = Path(fresh_db).with_name("t.txt")
        p.write_text(content, encoding="utf-8")
        read_template(p)
    conn.close()

    # idempotente: seconda esportazione non crea ne' sovrascrive nulla
    exp2 = client.post(f"/api/product_campaigns/{cid}/export_to_outreach").json()
    assert exp2["created"] == [] and len(exp2["existing"]) == 4


def test_ai_returning_wrong_count_cannot_leave_a_stuck_campaign(fresh_db, monkeypatch):
    """Regressione: prima si salvavano N-1 email su sequence_length=N e la campagna non era piu' approvabile."""
    _seed(fresh_db)
    monkeypatch.setattr("web_server.SalesStrategyAgent.generate",
                        lambda self, product_profile, market, language, target_segment, buyer_role: {**STRATEGY, "status": "SUCCESS"})
    client.post("/api/sales_strategy/generate", json=CTX)
    monkeypatch.setattr("product_intelligence.sales_strategy_agent.get_ai_provider", lambda db: _SeqProvider(_msgs(3)))
    res = client.post("/api/product_campaigns/generate", json={**CTX, "sequence_length": 4})
    assert res.status_code == 500 and "3 of 4" in res.json()["detail"]


# ─────────────────────────────────────────────────────────────── installazione da zero

def test_fresh_install_has_no_500s(tmp_path, monkeypatch):
    """Regressione: su un DB nuovo 7 endpoint su 22 rispondevano 500 (tabelle create solo da script manuali)."""
    from schema_bootstrap import ensure_all_schema
    db_path = tmp_path / "brand_new.sqlite3"
    ensure_all_schema(db_path)
    monkeypatch.setattr("web_server.DB_PATH", db_path)

    paths = sorted(r.path for r in app.routes
                   if getattr(r, "methods", None) and "GET" in r.methods and "{" not in r.path and r.path.startswith("/api"))
    failures = []
    for path in paths:
        res = client.get(path)
        if res.status_code >= 500:
            failures.append((path, res.status_code))
    assert failures == []


def test_schema_bootstrap_is_idempotent_and_keeps_data(fresh_db):
    from schema_bootstrap import ensure_all_schema
    _seed(fresh_db)
    ensure_all_schema(fresh_db)
    ensure_all_schema(fresh_db)
    conn = db_connector.get_connection(fresh_db)
    assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


# ─────────────────────────────────────────────────────────────── run_send_task (regressione reale)
# Bug trovato durante il collaudo dell'Address Book: AUDIT_PATH/SEND_LOG_PATH erano costanti fisse
# su ROOT invece che funzioni legate a DB_PATH. Sotto pytest questo (a) scriveva nei file reali del
# repository invece che nel DB temporaneo, e (b) un residuo `str(AUDIT_PATH)` con quel nome ormai
# non definito faceva fallire in silenzio ogni invio in background (NameError catturato da FastAPI
# BackgroundTasks, nessun errore visibile all'utente, i prospect restavano 'approved' per sempre).

def test_run_send_task_does_not_crash_and_logs_stay_with_the_db(fresh_db, tmp_path):
    import web_server
    conn = db_connector.get_connection(fresh_db)
    conn.execute("INSERT INTO templates (name, content, created_at_utc) VALUES ('t.txt', 'Subject: hi\n\nHello {company_name}', 'now')")
    conn.execute("INSERT INTO campaigns (name, template, created_at_utc) VALUES ('regression_send', 't.txt', 'now')")
    conn.commit()
    conn.close()
    _add_prospect(fresh_db, "hello@realagency.io", campaign="regression_send")

    web_server.run_send_task("regression_send", 5)  # non deve sollevare NameError ne' altro

    log_path = Path(fresh_db).with_name("campaign_send.log")
    audit_path = Path(fresh_db).with_name("outreach_audit.jsonl")
    assert log_path.exists(), "il log di invio deve stare accanto al DB, non nella cartella del codice"
    text = log_path.read_text()
    assert "Traceback" not in text and "NameError" not in text
