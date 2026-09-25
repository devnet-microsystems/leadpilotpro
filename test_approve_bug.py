from web_server import app, get_current_user
from fastapi.testclient import TestClient
import json

app.dependency_overrides[get_current_user] = lambda: {"username": "admin"}
client = TestClient(app)

from tests.test_p5_3b_sales_campaign_api import setup_mock_data, test_db, MockProvider

def test_manual():
    # Setup db using some temp file
    db_path = "temp_test.sqlite3"
    import sqlite3, os
    if os.path.exists(db_path): os.remove(db_path)
    # create tables via migrate
    from product_intelligence.sales_campaign_store import DDL
    conn = sqlite3.connect(db_path)
    conn.executescript(DDL)
    conn.commit()
    conn.close()
    
    # Actually just run the pytest but add print
