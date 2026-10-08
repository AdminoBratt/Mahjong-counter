import asyncio
import importlib
import re
import uuid
from contextlib import ExitStack

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import app.main


def test_health():
    r = TestClient(app.main.app).get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_cors_multiple_origins(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")
    client = TestClient(importlib.reload(app.main).app)
    for origin in ("http://a.test", "http://b.test"):
        r = client.get("/api/health", headers={"Origin": origin})
        assert r.headers["access-control-allow-origin"] == origin
    r = client.get("/api/health", headers={"Origin": "http://evil.test"})
    assert "access-control-allow-origin" not in r.headers
    monkeypatch.undo()
    importlib.reload(app.main)  # återställ modulen för andra tester


def test_spa_fallback(tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<html>spa</html>")
    (static / "favicon.svg").write_text("<svg/>")
    (tmp_path / "secret.txt").write_text("hemligt")
    spa = FastAPI()
    spa.mount("/", app.main.SPAStaticFiles(directory=static, html=True))
    client = TestClient(spa)
    assert client.get("/").text == "<html>spa</html>"
    assert client.get("/lobby/ABC123").text == "<html>spa</html>"
    assert client.get("/favicon.svg").text == "<svg/>"
    assert client.get("/api/finns-inte").status_code == 404
    assert "hemligt" not in client.get("/%2e%2e/secret.txt").text


def test_create_game():
    r = TestClient(app.main.app).post("/api/games")
    assert r.status_code == 201
    code = r.json()["lobby_code"]
    assert re.fullmatch(r"[A-HJ-NP-Z2-9]{6}", code)
    assert app.main.store.get(code) is not None


def test_join_game():
    client = TestClient(app.main.app)
    code = client.post("/api/games").json()["lobby_code"]
    r = client.post(f"/api/games/{code.lower()}/join", json={"nickname": "  Anna "})
    assert r.status_code == 200
    body = r.json()
    assert body["lobby_code"] == code
    assert body["rejoined"] is False
    assert body["players"] == [{"id": body["player_id"], "nickname": "Anna", "seat_order": 1}]

    r = client.post(f"/api/games/{code}/join", json={"nickname": "anna"})
    assert r.json()["rejoined"] is True
    assert r.json()["player_id"] == body["player_id"]


def test_join_errors():
    client = TestClient(app.main.app)
    code = client.post("/api/games").json()["lobby_code"]
    assert client.post("/api/games/NOPE00/join", json={"nickname": "A"}).status_code == 404
    for bad in ("", "   ", "x" * 21):
        assert client.post(f"/api/games/{code}/join", json={"nickname": bad}).status_code == 422
    for n in "ABCD":
        client.post(f"/api/games/{code}/join", json={"nickname": n})
    r = client.post(f"/api/games/{code}/join", json={"nickname": "E"})
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
    code = client.post("/api/games").json()["lobby_code"]
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
    code = client.post("/api/games").json()["lobby_code"]
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
    code = client.post("/api/games").json()["lobby_code"]
    with client.websocket_connect("/ws") as new:
        with client.websocket_connect("/ws") as old:
            _join(old, code, "Anna")
            _lobby(old)
            _join(new, code, "Anna")
            _lobby(new)
        assert app.main.store.get(code).players[0].connected is True


def test_ws_origin_check():
    client = TestClient(app.main.app)  # host-header: "testserver"
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect("/ws", headers={"Origin": "https://evil.test"}):
            pass
    assert e.value.code == 1008
    for headers in (
        {"Origin": "http://localhost:5173"},  # CORS_ORIGINS (Vite lokalt)
        {"Origin": "https://testserver"},  # samma host
        {"Origin": "https://app.test", "X-Forwarded-Host": "app.test"},  # bakom proxy
    ):
        with client.websocket_connect("/ws", headers=headers) as ws:
            ws.send_text("inte json")
            assert ws.receive_json()["code"] == "invalid_message"  # släpptes in


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
    code = client.post("/api/games").json()["lobby_code"]
    join = {"type": "join_lobby", "lobby_code": code}
    assert _ws_error(client, text="inte json") == "invalid_message"
    assert _ws_error(client, payload=[1]) == "invalid_message"
    assert _ws_error(client, payload={"type": "end_game"}) == "invalid_message"
    assert _ws_error(client, payload={**join, "nickname": "   "}) == "invalid_nickname"
    assert _ws_error(client, payload={**join, "nickname": "x" * 21}) == "invalid_nickname"
    assert _ws_error(client, payload={**join, "lobby_code": "NOPE00", "nickname": "A"}) == "unknown_lobby"

    for n in "ABCD":
        client.post(f"/api/games/{code}/join", json={"nickname": n})
    assert _ws_error(client, payload={**join, "nickname": "E"}) == "game_full"

    started = client.post("/api/games").json()["lobby_code"]
    client.post(f"/api/games/{started}/join", json={"nickname": "A"})
    app.main.store.get(started).status = "active"
    assert _ws_error(client, payload={**join, "lobby_code": started, "nickname": "B"}) == "game_started"

    monkeypatch.setattr(app.main, "JOIN_TIMEOUT", 0.1)
    assert _ws_error(client) == "invalid_message"


def test_ws_choose_wind_broadcast_and_garbage_ignored():
    client = TestClient(app.main.app)
    code = client.post("/api/games").json()["lobby_code"]
    for n in "ABCD":
        client.post(f"/api/games/{code}/join", json={"nickname": n})
    with client.websocket_connect("/ws") as a, client.websocket_connect("/ws") as b:
        _join(a, code, "A")
        _lobby(a)
        _join(b, code, "B")
        _lobby(a)
        _, msg = _lobby(b)
        assert msg["status"] == "waiting" and msg["players"][0]["wind"] is None

        # Skräp stänger aldrig socketen och ger inget svar.
        a.send_text("inte json")
        a.send_json([1])
        a.send_json("sträng")
        a.send_json({"type": "choose_wind", "wind": "up"})
        a.send_bytes(b"\x00binar")

        a.send_json({"type": "choose_wind", "wind": "east"})
        _, msg = _lobby(a)
        assert b.receive_json() == msg
        assert [p["wind"] for p in msg["players"]] == ["east", None, None, None]

        b.send_json({"type": "choose_wind", "wind": "east"})  # tagen: nekas men synkas
        _, msg = _lobby(b)
        assert a.receive_json() == msg and msg["players"][1]["wind"] is None

        game = app.main.store.get(code)
        game.players[2].wind, game.players[3].wind = "west", "north"
        b.send_json({"type": "choose_wind", "wind": "south"})
        _, msg = _lobby(b)
        assert a.receive_json() == msg and msg["status"] == "active"


# --- 3.4b: submit_score / round_complete ---

WINNER = {"chows": 4, "mahjong": {}}  # 20 + 10 (bara följder) = 30p
LOSER = {"sets": [{"size": 3, "concealed": False, "major": False}]}  # 2p


def _start(client, stack):
    """Fyra spelare A-D ansluter och väljer öst/syd/väst/nord. Returnerar (kod, sockets, ids, sista lobby_update)."""
    code = client.post("/api/games").json()["lobby_code"]
    socks = []
    for n in "ABCD":
        ws = stack.enter_context(client.websocket_connect("/ws"))
        socks.append(ws)
        _join(ws, code, n)
        for s in socks:
            _lobby(s)
    for ws, wind in zip(socks, ("east", "south", "west", "north")):
        ws.send_json({"type": "choose_wind", "wind": wind})
        msgs = [_lobby(s)[1] for s in socks]
    assert msgs[0]["status"] == "active" and all(m == msgs[0] for m in msgs)
    return code, socks, [p["id"] for p in msgs[0]["players"]], msgs[0]


def _submit(ws, rnd, score_input, draw=False):
    ws.send_json({"type": "submit_score", "round_id": rnd["id"], "score_input": score_input, "draw": draw})


def _all(socks, type_):
    """Nästa meddelande på varje socket måste vara type_ och lika för alla."""
    msgs = [s.receive_json() for s in socks]
    assert all(m == msgs[0] for m in msgs) and msgs[0]["type"] == type_, msgs
    return msgs[0]


def test_ws_full_round():
    client = TestClient(app.main.app)
    with ExitStack() as stack:
        code, socks, ids, msg = _start(client, stack)
        rnd = msg["current_round"]
        assert rnd["round_number"] == 1 and rnd["round_wind"] == "east"
        assert rnd["conflict"] is None and rnd["submissions"] == {}

        # D (nord) vinner 30p. A-C 2p var. Förlorarna lika -> inget sinsemellan.
        for i, ws in enumerate(socks[:3]):
            _submit(ws, rnd, LOSER)
            cur = _all(socks, "lobby_update")["current_round"]
            assert set(cur["submissions"]) == set(ids[: i + 1]) and cur["conflict"] is None
            assert cur["submissions"][ids[i]]["final_points"] == 2
        _submit(socks[3], rnd, WINNER)

        done = _all(socks, "round_complete")  # före nya lobby_update
        assert done["round_id"] == rnd["id"] and done["round_number"] == 1
        assert done["winner_id"] == ids[3]
        assert done["payments"][ids[3]] == {
            "base_points": 30, "doublings": 0, "final_points": 30, "payment_delta": 120,
        }
        assert done["new_totals"] == dict(zip(ids, [-60, -30, -30, 120]))
        assert done["next_round_winds"] == dict(zip(ids, ["north", "east", "south", "west"]))

        nxt = _all(socks, "lobby_update")
        assert nxt["current_round"]["round_number"] == 2
        assert nxt["current_round"]["id"] != rnd["id"] and nxt["current_round"]["submissions"] == {}
        assert [p["wind"] for p in nxt["players"]] == ["north", "east", "south", "west"]
        assert [p["total_score"] for p in nxt["players"]] == [-60, -30, -30, 120]


def test_ws_conflict_resolved():
    client = TestClient(app.main.app)
    with ExitStack() as stack:
        code, socks, ids, msg = _start(client, stack)
        rnd = msg["current_round"]
        for ws, inp in zip(socks, (WINNER, LOSER, LOSER, WINNER)):
            _submit(ws, rnd, inp)
            cur = _all(socks, "lobby_update")["current_round"]
        assert cur["conflict"] == "multiple_mahjong" and len(cur["submissions"]) == 4

        _submit(socks[3], rnd, LOSER)  # D ångrar sin Mahjong
        done = _all(socks, "round_complete")
        assert done["winner_id"] == ids[0]
        assert _all(socks, "lobby_update")["current_round"]["round_number"] == 2


def test_ws_rejoin_gets_own_submission():
    client = TestClient(app.main.app)
    with ExitStack() as stack:
        code, socks, ids, msg = _start(client, stack)
        rnd = msg["current_round"]
        _submit(socks[1], rnd, LOSER, draw=True)
        _all(socks, "lobby_update")
        socks[1].close()
        cur = _all([socks[0], socks[2], socks[3]], "lobby_update")  # B frånkopplad
        assert cur["players"][1]["connected"] is False

        b = stack.enter_context(client.websocket_connect("/ws"))
        _join(b, code, "b")
        mine = _lobby(b)[1]["current_round"]["submissions"][ids[1]]
        # Uträkningen följer med, så klienten kan visa den utan att räkna själv.
        assert mine == {
            "draw": True, "score_input": LOSER, "base_points": 2, "doublings": 0, "final_points": 2,
        }


def test_ws_game_errors_only_to_sender():
    client = TestClient(app.main.app)
    with ExitStack() as stack:
        # not_active: före vindvalet.
        code = client.post("/api/games").json()["lobby_code"]
        a = stack.enter_context(client.websocket_connect("/ws"))
        _join(a, code, "A")
        _lobby(a)
        a.send_json({"type": "submit_score", "round_id": str(uuid.uuid4()), "score_input": {}})
        assert a.receive_json()["code"] == "not_active"

        code, socks, ids, msg = _start(client, stack)
        rnd = msg["current_round"]
        bad = [
            ({**rnd, "id": str(uuid.uuid4())}, LOSER, False, "wrong_round"),
            (rnd, {"chows": 5}, False, "invalid_score"),
            (rnd, WINNER, True, "invalid_score"),  # oavgjort + Mahjong
            (rnd, "inte ett objekt", False, "invalid_message"),
            ({"id": "inte-uuid"}, LOSER, False, "invalid_message"),
            (rnd, LOSER, "ja", "invalid_message"),  # draw måste vara bool
        ]
        for r, inp, draw, err in bad:
            _submit(socks[0], r, inp, draw)
            got = socks[0].receive_json()
            assert got["type"] == "error" and got["code"] == err and got["message"]
        socks[0].send_json({"type": "end_game"})  # okänd typ: ignoreras, inget svar

        # Socketen lever, och de andra fick inget error: nästa meddelande är broadcasten.
        _submit(socks[0], rnd, LOSER)
        assert list(_all(socks, "lobby_update")["current_round"]["submissions"]) == [ids[0]]


def test_send_timeout_closes_socket(monkeypatch):
    monkeypatch.setattr(app.main, "SEND_TIMEOUT", 0.01)

    class Slow:
        closed = False

        async def send_json(self, msg):
            await asyncio.sleep(1)

        async def close(self):
            self.closed = True

    ws = Slow()
    asyncio.run(app.main._send(ws, {}))
    assert ws.closed
