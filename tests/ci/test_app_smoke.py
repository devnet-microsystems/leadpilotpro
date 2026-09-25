import os

import web_server
from fastapi.testclient import TestClient


def _authenticated_client():
    web_server.app.dependency_overrides[web_server.get_current_user] = (
        lambda: {"id": 1, "username": "admin"}
    )
    return TestClient(web_server.app)


def test_health_and_public_shell():
    client = TestClient(web_server.app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    os.environ["LEADPILOT_DISABLE_AUTH"] = "1"
    try:
        root = client.get("/")
        assert root.status_code == 200
        assert "Find Customers" in root.text
    finally:
        os.environ.pop("LEADPILOT_DISABLE_AUTH", None)


def test_product_crud_smoke():
    from product_intelligence.store import ensure_schema

    ensure_schema(str(web_server.DB_PATH))
    client = _authenticated_client()
    try:
        created = client.post("/api/products", json={"name": "CI Smoke Product"})
        assert created.status_code == 200, created.text
        product = created.json()
        assert product["name"] == "CI Smoke Product"
        product_id = product["id"]

        listed = client.get("/api/products")
        assert listed.status_code == 200
        assert any(p["id"] == product_id for p in listed.json())

        detail = client.get(f"/api/products/{product_id}")
        assert detail.status_code == 200
        assert detail.json()["id"] == product_id
    finally:
        web_server.app.dependency_overrides.pop(web_server.get_current_user, None)
