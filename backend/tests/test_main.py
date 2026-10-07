import importlib

from fastapi.testclient import TestClient

import app.main


def test_health():
    r = TestClient(app.main.app).get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_cors_multiple_origins(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")
    client = TestClient(importlib.reload(app.main).app)
    for origin in ("http://a.test", "http://b.test"):
        r = client.get("/health", headers={"Origin": origin})
        assert r.headers["access-control-allow-origin"] == origin
    r = client.get("/health", headers={"Origin": "http://evil.test"})
    assert "access-control-allow-origin" not in r.headers
    monkeypatch.undo()
    importlib.reload(app.main)  # återställ modulen för andra tester
