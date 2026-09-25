import json

from product_intelligence.store import create_product, ensure_schema, save_product_analysis
from web_server import load_product_profile


def test_sales_pipeline_loads_persisted_product_profile(tmp_path, monkeypatch):
    monkeypatch.delenv("LEADPILOT_DB_URL", raising=False)
    db_path = str(tmp_path / "leadpilot.sqlite3")
    ensure_schema(db_path)

    product = create_product(db_path, "Test Product")
    profile = {
        "product_name": "Test Product",
        "short_description": "Evidence-backed profile",
        "key_features": [],
        "problems_solved": [],
    }
    save_product_analysis(db_path, product["id"], profile, "test-provider", "test-model")

    persisted_product, persisted_profile = load_product_profile(db_path, product["id"])

    assert persisted_product["status"] == "READY"
    assert json.loads(persisted_product["raw_summary"]) == profile
    assert persisted_profile == profile
