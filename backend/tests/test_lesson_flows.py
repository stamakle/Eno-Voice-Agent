from fastapi.testclient import TestClient
from english_tech.main import app

client = TestClient(app)

def test_get_lesson_requires_auth():
    response = client.get("/api/lesson/course1/chapter1/lesson1")
    assert response.status_code == 401

def test_complete_lesson_requires_auth():
    response = client.post("/api/lesson/complete", json={})
    assert response.status_code == 401
