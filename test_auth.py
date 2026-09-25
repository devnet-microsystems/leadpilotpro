from web_server import app, get_current_user
from fastapi.testclient import TestClient

app.dependency_overrides[get_current_user] = lambda: {"username": "admin"}
client = TestClient(app)

res = client.get("/api/research_campaigns")
print(res.status_code, res.text)
