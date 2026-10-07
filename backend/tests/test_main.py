import importlib
import re

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

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


def _join(ws, code, nickname):
    ws.send_json({"type": "join_lobby", "lobby_code": code, "nickname": nickname})


def _lobby(ws):
    """Nästa meddelande måste vara lobby_update; returnerar (namn, connected)-par."""
    msg = ws.receive_json()
    assert msg["type"] == "lobby_update"
    assert [p["seat_order"] for p in msg["players"]] == list(range(1, len(msg["players"]) + 1))
    return [(p["nickname"], p["connected"]) for p in msg["players"]], msg


def test_ws_join_disconnect_rejoin():
    client = TestClient(app.main.app)
    code = client.post("/games").json()["lobby_code"]
    with client.websocket_connect("/ws") as a:
        _join(a, code, "Anna")
        assert _lobby(a)[0] == [("Anna", True)]

        with client.websocket_connect("/ws") as b:
            _join(b, code.lower(), " Bo ")
            both = [("Anna", True), ("Bo", True)]
            assert _lobby(a)[0] == both
            players, msg = _lobby(b)
            assert players == both
            bo_id = msg["players"][1]["id"]

        assert _lobby(a)[0] == [("Anna", True), ("Bo", False)]

        with client.websocket_connect("/ws") as b2:
            _join(b2, code, "BO")
            players, msg = _lobby(b2)
            assert players == [("Anna", True), ("Bo", True)]
            assert msg["players"][1]["id"] == bo_id
            assert a.receive_json() == msg


def test_ws_same_player_new_socket_replaces_old():
    client = TestClient(app.main.app)
    code = client.post("/games").json()["lobby_code"]
    with client.websocket_connect("/ws") as old:
        _join(old, code, "Anna")
        assert _lobby(old)[0] == [("Anna", True)]
        with client.websocket_connect("/ws") as new:
            _join(new, code, "anna")
            assert _lobby(new)[0] == [("Anna", True)]
            with pytest.raises(WebSocketDisconnect):
                old.receive_json()
    # Den gamla socketens nedkoppling får inte markera spelaren som frånkopplad
    # medan den nya var aktiv; först när den nya stängs.
    assert app.main.store.get(code).players[0].connected is False


def test_ws_old_socket_close_keeps_player_connected():
    client = TestClient(app.main.app)
    code = client.post("/games").json()["lobby_code"]
    with client.websocket_connect("/ws") as new:
        with client.websocket_connect("/ws") as old:
            _join(old, code, "Anna")
            _lobby(old)
            _join(new, code, "Anna")
            _lobby(new)
        assert app.main.store.get(code).players[0].connected is True


def _ws_error(client, payload=None, text=None):
    with client.websocket_connect("/ws") as ws:
        if text is not None:
            ws.send_text(text)
        elif payload is not None:
            ws.send_json(payload)
        msg = ws.receive_json()
        assert msg["type"] == "error" and msg["message"]
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
        return msg["code"]


def test_ws_errors(monkeypatch):
    client = TestClient(app.main.app)
    code = client.post("/games").json()["lobby_code"]
    join = {"type": "join_lobby", "lobby_code": code}
    assert _ws_error(client, text="inte json") == "invalid_message"
    assert _ws_error(client, payload=[1]) == "invalid_message"
    assert _ws_error(client, payload={"type": "end_game"}) == "invalid_message"
    assert _ws_error(client, payload={**join, "nickname": "   "}) == "invalid_nickname"
    assert _ws_error(client, payload={**join, "nickname": "x" * 21}) == "invalid_nickname"
    assert _ws_error(client, payload={**join, "lobby_code": "NOPE00", "nickname": "A"}) == "unknown_lobby"

    for n in "ABCD":
        client.post(f"/games/{code}/join", json={"nickname": n})
    assert _ws_error(client, payload={**join, "nickname": "E"}) == "game_full"

    started = client.post("/games").json()["lobby_code"]
    client.post(f"/games/{started}/join", json={"nickname": "A"})
    app.main.store.get(started).status = "active"
    assert _ws_error(client, payload={**join, "lobby_code": started, "nickname": "B"}) == "game_started"

    monkeypatch.setattr(app.main, "JOIN_TIMEOUT", 0.1)
    assert _ws_error(client) == "invalid_message"
