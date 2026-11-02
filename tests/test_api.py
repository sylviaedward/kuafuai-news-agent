from fastapi.testclient import TestClient

from app.main import app


def test_local_ui_subscription_and_missing_model(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("OPENAI_COMPAT_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_COMPAT_MODEL", raising=False)
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        response = client.post("/api/users", json={"name": " Lin ", "email": "lin@example.com",
            "topics": ["Agent"], "keywords": ["RAG"], "delivery_hour": 9})
        assert response.status_code == 200
        user = response.json()
        assert user["name"] == "Lin"
        assert client.get(f"/api/users/{user['id']}/runs").json() == []
        assert client.post(f"/api/users/{user['id']}/runs").status_code == 503
