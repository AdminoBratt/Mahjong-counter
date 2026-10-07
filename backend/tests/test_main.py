import importlib
import re

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


def test_create_game():
    r = TestClient(app.main.app).post("/games")
    assert r.status_code == 201
    code = r.json()["lobby_code"]
    assert re.fullmatch(r"[A-HJ-NP-Z2-9]{6}", code)
    assert app.main.store.get(code) is not None


def test_join_game():
    client = TestClient(app.main.app)
    code = client.post("/games").json()["lobby_code"]
    r = client.post(f"/games/{code.lower()}/join", json={"nickname": "  Anna "})
    assert r.status_code == 200
    body = r.json()
    assert body["lobby_code"] == code
    assert body["rejoined"] is False
    assert body["players"] == [{"id": body["player_id"], "nickname": "Anna", "seat_order": 1}]

    r = client.post(f"/games/{code}/join", json={"nickname": "anna"})
    assert r.json()["rejoined"] is True
    assert r.json()["player_id"] == body["player_id"]


def test_join_errors():
    client = TestClient(app.main.app)
    code = client.post("/games").json()["lobby_code"]
    assert client.post("/games/NOPE00/join", json={"nickname": "A"}).status_code == 404
    for bad in ("", "   ", "x" * 21):
        assert client.post(f"/games/{code}/join", json={"nickname": bad}).status_code == 422
    for n in "ABCD":
        client.post(f"/games/{code}/join", json={"nickname": n})
    r = client.post(f"/games/{code}/join", json={"nickname": "E"})
    assert r.status_code == 409
