from fastapi.testclient import TestClient
from english_tech.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    # Note: /health might not be the exact path if it's mounted differently, but main.py includes health_router
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
