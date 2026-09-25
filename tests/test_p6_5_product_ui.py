import pytest
from fastapi.testclient import TestClient
from web_server import app, get_current_user
from schema_bootstrap import ensure_all_schema
from outreach_sender import OutreachDatabase
from pathlib import Path
import os
import sqlite3

# Mock auth
app.dependency_overrides[get_current_user] = lambda: {"username": "admin"}
client = TestClient(app)

def test_product_tab_ui_presence():
    """Verify Products tab and modal exist in HTML"""
    with open("static/index.html", "r", encoding="utf-8") as f:
        html = f.read()
    
    assert "Products / Product Intelligence" in html
    assert "add-product-name" in html
    assert "submitNewProduct()" in html

def test_product_js_logic():
    """Verify the frontend API contract matches the backend routes"""
    with open("static/products.js", "r", encoding="utf-8") as f:
        js = f.read()
    
    assert "fetch('/api/products'" in js
    assert "fetch(`/api/products/${productId}/sources`" in js
    assert "fetch(`/api/products/${productId}/analyze`" in js

def test_product_creation_api_flow(tmp_path):
    """Verify we can create a product and add a source through the APIs used by the UI"""
    db_path = tmp_path / "test_products.sqlite3"
    # Create the schema
    db = OutreachDatabase(db_path)
    ensure_all_schema(db_path)
    
    # We must patch DB_PATH for the test client
    import web_server
    original_db = web_server.DB_PATH
    web_server.DB_PATH = db_path
    
    # Mock extract_from_url to avoid network requests during test
    from product_intelligence.models import ProductSourceContent
    from enum import Enum
    class SourceType(Enum):
        URL = "URL"
    original_extract = web_server.extract_from_url
    web_server.extract_from_url = lambda url: ProductSourceContent(
        source_type=SourceType.URL,
        source_name="Mocked URL",
        content_hash="mock-hash",
        extracted_text="Mocked content from " + url,
        source_url=url
    )
    
    try:
        # 1. Create Product
        res = client.post("/api/products", json={"name": "Test Security Product"})
        assert res.status_code == 200
        product_id = res.json()["id"]
        
        # 2. Add Source URL
        res = client.post(f"/api/products/{product_id}/sources", json={
            "source_type": "URL",
            "content": "https://example.com/security"
        })
        assert res.status_code == 200, res.json()
        
        # 3. Trigger analyze (in background)
        res = client.post(f"/api/products/{product_id}/analyze")
        assert res.status_code == 200
        
        # 4. Verify product list
        res = client.get("/api/products")
        assert res.status_code == 200
        products = res.json()
        assert len(products) == 1
        assert products[0]["name"] == "Test Security Product"
        assert products[0]["status"] in ["ANALYZING", "DRAFT", "FAILED"]
        
        # 5. Verify orchestrator uses it (Sell This Product)
        # The orchestrator JS calls /api/products directly to build the selector
        with open("static/orchestrator.js", "r", encoding="utf-8") as f:
            js = f.read()
            assert "fetch('/api/products')" in js
            
    finally:
        web_server.DB_PATH = original_db
        web_server.extract_from_url = original_extract
