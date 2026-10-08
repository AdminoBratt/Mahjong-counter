import asyncio
import importlib
import logging
import re
import uuid
from contextlib import ExitStack
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import app.main
from app.store import FINISHED_GAME_TTL, IDLE_GAME_TTL, MAX_IDLE, WAITING_GAME_TTL, GameStore, _now


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
    msg = {"type": "submit_score", "round_id": rnd["id"], "draw": draw}
    if score_input is not None:
        msg["score_input"] = score_input
    ws.send_json(msg)


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
        assert done["round_wind"] == "east"
        assert done["payments"][ids[3]] == {
            "wind": "north", "base_points": 30, "doublings": 0, "final_points": 30, "payment_delta": 120,
        }
        assert done["new_totals"] == dict(zip(ids, [-60, -30, -30, 120]))
        assert done["next_round_winds"] == dict(zip(ids, ["north", "east", "south", "west"]))

        nxt = _all(socks, "lobby_update")
        assert nxt["current_round"]["round_number"] == 2
        assert nxt["current_round"]["id"] != rnd["id"] and nxt["current_round"]["submissions"] == {}
        assert [p["wind"] for p in nxt["players"]] == ["north", "east", "south", "west"]
        assert [p["total_score"] for p in nxt["players"]] == [-60, -30, -30, 120]


LOSER_4 = {"sets": [{"size": 3, "concealed": True, "major": False}]}  # 4p
LOSER_8 = {"sets": [{"size": 3, "concealed": True, "major": True}]}  # 8p


def _play(socks, rnd, inputs):
    """Alla fyra lämnar in. Returnerar (round_complete, följande lobby_update)."""
    for i, (ws, inp) in enumerate(zip(socks, inputs)):
        _submit(ws, rnd, inp)
        if i < 3:
            _all(socks, "lobby_update")
    return _all(socks, "round_complete"), _all(socks, "lobby_update")


def test_ws_last_round_live_equals_reload():
    client = TestClient(app.main.app)
    with ExitStack() as stack:
        code, socks, ids, msg = _start(client, stack)
        assert msg["last_round"] is None
        assert msg["score_history"] == {i: [0] for i in ids}

        # Rond 1: D (nord) vinner 30p. A (öst) 4p, B 2p, C 8p, så förlorarna gör upp och Öst dubblas.
        done, nxt = _play(socks, msg["current_round"], (LOSER_4, LOSER, LOSER_8, WINNER))
        deltas = [done["payments"][i]["payment_delta"] for i in ids]
        assert deltas == [-64, -40, -16, 120] and sum(deltas) == 0
        assert [done["payments"][i]["wind"] for i in ids] == ["east", "south", "west", "north"]
        live = {k: v for k, v in done.items() if k != "type"}
        assert nxt["last_round"] == live
        history = nxt["score_history"]
        assert history == dict(zip(ids, [[0, -64], [0, -40], [0, -16], [0, 120]]))

        # Omladdning: samma resultat och samma historik.
        socks[1].close()
        _all([socks[0], socks[2], socks[3]], "lobby_update")
        b = stack.enter_context(client.websocket_connect("/ws"))
        _join(b, code, "b")
        socks[1] = b
        reloaded = _all(socks, "lobby_update")
        assert reloaded["last_round"] == live
        assert reloaded["score_history"] == history

        # Rond 2: B är nu Öst och vinner. Vindarna står kvar, last_round byter till rond 2.
        done2, nxt2 = _play(socks, nxt["current_round"], (LOSER, WINNER, LOSER_4, LOSER_8))
        assert done2["round_number"] == 2 and done2["winner_id"] == ids[1]
        deltas2 = [done2["payments"][i]["payment_delta"] for i in ids]
        assert deltas2 == [-68, 180, -62, -50] and sum(deltas2) == 0
        assert nxt2["last_round"] == {k: v for k, v in done2.items() if k != "type"}
        assert nxt2["last_round"]["new_totals"] == dict(zip(ids, [-132, 140, -78, 70]))
        assert nxt2["last_round"]["next_round_winds"] == dict(zip(ids, ["north", "east", "south", "west"]))
        h2 = nxt2["score_history"]
        assert {i: s[-1] for i, s in h2.items()} == nxt2["last_round"]["new_totals"]
        assert all(len(s) == 3 and s[:2] == history[i] for i, s in h2.items())
        assert all(sum(s[r] for s in h2.values()) == 0 for r in range(3))


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
            "draw": True, "mahjong": False, "score_input": LOSER, "base_points": 2, "doublings": 0, "final_points": 2,
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
            (rnd, None, False, "invalid_message"),  # varken score_input eller final_points
        ]
        for r, inp, draw, err in bad:
            _submit(socks[0], r, inp, draw)
            got = socks[0].receive_json()
            assert got["type"] == "error" and got["code"] == err and got["message"]
        socks[0].send_json({"type": "mark_mahjong"})  # okänd typ: ignoreras, inget svar

        # Socketen lever, och de andra fick inget error: nästa meddelande är broadcasten.
        _submit(socks[0], rnd, LOSER)
        assert list(_all(socks, "lobby_update")["current_round"]["submissions"]) == [ids[0]]


# --- 3.9a: slutpoäng angiven direkt ---

# Öst: 3tal 1,9,vind,drake på hand (8) + på bordet (4) = 12p, ett drak-3tal 1× = 24p.
EAST_24 = {
    "sets": [{"size": 3, "concealed": True, "major": True}, {"size": 3, "concealed": False, "major": True}],
    "dragon_sets": 1,
}
# Syd: två 3tal 2-8 på hand = 8p.
SOUTH_8 = {"sets": [{"size": 3, "concealed": True, "major": False}] * 2}


def _direct(ws, rnd, points, mahjong=False):
    ws.send_json({"type": "submit_score", "round_id": rnd["id"], "final_points": points, "mahjong": mahjong})


def test_ws_direct_score_errors():
    client = TestClient(app.main.app)
    with ExitStack() as stack:
        code, socks, ids, msg = _start(client, stack)
        rid = msg["current_round"]["id"]
        base = {"type": "submit_score", "round_id": rid}
        bad = [
            ({"final_points": True}, "invalid_message"),  # bool är inte ett heltal
            ({"final_points": 48.0}, "invalid_message"),
            ({"final_points": "48"}, "invalid_message"),
            ({"final_points": 48, "score_input": {}}, "invalid_message"),  # båda
            ({"score_input": {}, "mahjong": True}, "invalid_message"),  # mahjong hör till final_points
            ({"final_points": 0, "draw": True}, "invalid_message"),
            ({"final_points": 48, "mahjong": "ja"}, "invalid_message"),
            ({"final_points": -2}, "invalid_score"),
            ({"final_points": 47}, "invalid_score"),
            ({"final_points": 18, "mahjong": True}, "invalid_score"),
        ]
        for extra, err in bad:
            socks[0].send_json({**base, **extra})
            got = socks[0].receive_json()
            assert got["type"] == "error" and got["code"] == err and got["message"], extra

        _direct(socks[0], msg["current_round"], 20, mahjong=True)  # socketen lever
        mine = _all(socks, "lobby_update")["current_round"]["submissions"][ids[0]]
        assert mine == {
            "draw": False, "mahjong": True, "score_input": None, "base_points": None, "doublings": None, "final_points": 20,
        }


def test_ws_mixed_round_live_equals_reload():
    """Exemplet i spelregler.md: Nord vinner 48p, Öst 24p, Syd 8p, Väst 32p.
    Nord och Väst anger slutpoängen direkt, Öst och Syd via vyerna."""
    client = TestClient(app.main.app)
    with ExitStack() as stack:
        code, socks, ids, msg = _start(client, stack)
        rnd = msg["current_round"]
        _submit(socks[0], rnd, EAST_24)
        _all(socks, "lobby_update")
        _submit(socks[1], rnd, SOUTH_8)
        _all(socks, "lobby_update")
        _direct(socks[2], rnd, 32)
        # Tre av fyra inne, en direkt: ronden pågår och historiken är oförändrad.
        assert _all(socks, "lobby_update")["score_history"] == {i: [0] for i in ids}
        _direct(socks[3], rnd, 48, mahjong=True)

        done = _all(socks, "round_complete")
        nxt = _all(socks, "lobby_update")
        assert done["winner_id"] == ids[3]
        pay = done["payments"]
        deltas = [pay[i]["payment_delta"] for i in ids]
        assert deltas == [-80, -104, -8, 192] and sum(deltas) == 0
        assert [pay[i]["final_points"] for i in ids] == [24, 8, 32, 48]
        assert [(pay[i]["base_points"], pay[i]["doublings"]) for i in ids] == [(12, 1), (8, 0), (None, None), (None, None)]
        assert done["new_totals"] == dict(zip(ids, [-80, -104, -8, 192]))
        assert done["next_round_winds"] == dict(zip(ids, ["north", "east", "south", "west"]))
        live = {k: v for k, v in done.items() if k != "type"}
        assert nxt["last_round"] == live
        history = dict(zip(ids, [[0, -80], [0, -104], [0, -8], [0, 192]]))
        assert nxt["score_history"] == history

        # Omladdning: samma resultat och samma historik.
        socks[3].close()
        _all(socks[:3], "lobby_update")
        d = stack.enter_context(client.websocket_connect("/ws"))
        _join(d, code, "D")
        socks[3] = d
        reloaded = _all(socks, "lobby_update")
        assert reloaded["last_round"] == live
        assert reloaded["score_history"] == history


def test_send_timeout_closes_socket(monkeypatch):
    monkeypatch.setattr(app.main, "SEND_TIMEOUT", 0.01)

    class Slow:
        closed = False

        async def send_json(self, msg):
            await asyncio.sleep(1)

        async def close(self, code=1000):
            self.closed = True

    ws = Slow()
    asyncio.run(app.main._send(ws, {}))
    assert ws.closed


def test_ws_end_game_live_equals_reload():
    client = TestClient(app.main.app)
    with ExitStack() as stack:
        code, socks, ids, msg = _start(client, stack)
        _, nxt = _play(socks, msg["current_round"], (LOSER_4, LOSER, LOSER_8, WINNER))
        _, nxt = _play(socks, nxt["current_round"], (LOSER, WINNER, LOSER_4, LOSER_8))
        history = nxt["score_history"]
        # Rond 3 pågår: A har lämnat in.
        _submit(socks[0], nxt["current_round"], LOSER)
        _all(socks, "lobby_update")

        # Bara skaparen (A, plats 1) får avsluta. Felet går bara till B.
        socks[1].send_json({"type": "end_game"})
        assert socks[1].receive_json()["code"] == "not_host"

        socks[0].send_json({"type": "end_game"})
        over = _all(socks, "game_over")  # före lobby_update, som round_complete
        final = _all(socks, "lobby_update")
        live = {k: v for k, v in over.items() if k != "type"}
        assert final["status"] == "finished" and final["current_round"] is None
        assert final["final_result"] == live
        assert live["rounds_played"] == 2 and live["ended_by"] == ids[0]
        assert live["standings"] == [
            {"player_id": ids[1], "place": 1, "total_score": 140},
            {"player_id": ids[3], "place": 2, "total_score": 70},
            {"player_id": ids[2], "place": 3, "total_score": -78},
            {"player_id": ids[0], "place": 4, "total_score": -132},
        ]
        assert final["score_history"] == history  # rond 3 räknas inte

        # Omladdning: identiskt slutresultat.
        socks[2].close()
        _all([socks[0], socks[1], socks[3]], "lobby_update")
        c = stack.enter_context(client.websocket_connect("/ws"))
        _join(c, code, "C")
        socks[2] = c
        reloaded = _all(socks, "lobby_update")
        assert reloaded["final_result"] == live and reloaded["score_history"] == history

        # choose_wind ignoreras tyst. submit_score och end_game ger fel bara till avsändaren.
        socks[3].send_json({"type": "choose_wind", "wind": "east"})
        _submit(socks[3], nxt["current_round"], LOSER)
        assert socks[3].receive_json()["code"] == "game_finished"
        socks[0].send_json({"type": "end_game"})
        assert socks[0].receive_json()["code"] == "game_finished"

        # Nytt smeknamn nekas.
        assert _ws_error(client, {"type": "join_lobby", "lobby_code": code, "nickname": "E"}) == "game_finished"


# --- 4.5: städning ---
# cleanup(now) anropas med en framtida tid, på serverns event-loop via client.portal. Ingen väntan på riktig tid.

SECOND = timedelta(seconds=1)


def _closed_with(ws):
    with pytest.raises(WebSocketDisconnect) as e:
        while True:
            ws.receive_json()
    return e.value.code


def test_cleanup_finished_game_closes_sockets_with_4000():
    with TestClient(app.main.app) as client, ExitStack() as stack:
        code, socks, _, _ = _start(client, stack)
        socks[0].send_json({"type": "end_game"})
        _all(socks, "game_over")
        _all(socks, "lobby_update")
        ended = app.main.store.get(code).last_activity

        client.portal.call(app.main.cleanup, ended + FINISHED_GAME_TTL)
        assert app.main.store.get(code) is not None
        client.portal.call(app.main.cleanup, ended + FINISHED_GAME_TTL + SECOND)
        assert [_closed_with(ws) for ws in socks] == [4000] * 4
        assert app.main.store.get(code) is None
        assert code not in app.main.connections and code not in app.main.locks
        assert _ws_error(client, {"type": "join_lobby", "lobby_code": code, "nickname": "A"}) == "unknown_lobby"


def test_cleanup_keeps_connected_rescued_by_rejoin_and_max_idle_4001():
    with TestClient(app.main.app) as client:
        with ExitStack() as stack:
            code, _, _, _ = _start(client, stack)
            game = app.main.store.get(code)
            client.portal.call(app.main.cleanup, game.last_activity + MAX_IDLE)
            assert app.main.store.get(code) is game  # lång paus, men någon är ansluten
        gone = game.disconnected_since  # alla har kopplat från
        assert gone is not None

        client.portal.call(app.main.cleanup, gone + IDLE_GAME_TTL)
        assert app.main.store.get(code) is game
        with client.websocket_connect("/ws") as a:
            _join(a, code, "A")
            _lobby(a)
            assert game.disconnected_since is None
            client.portal.call(app.main.cleanup, gone + IDLE_GAME_TTL + SECOND)
            assert app.main.store.get(code) is game  # räddat av återanslutningen

            # Taket gäller även med en ansluten spelare.
            client.portal.call(app.main.cleanup, game.last_activity + MAX_IDLE + SECOND)
            assert _closed_with(a) == 4001
        assert app.main.store.get(code) is None
        assert code not in app.main.connections and code not in app.main.locks


def test_cleanup_memory_does_not_grow(monkeypatch, caplog):
    store = GameStore()
    monkeypatch.setattr(app.main, "store", store)
    codes = [store.create().lobby_code for _ in range(1000)]
    assert len(store) == 1000
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    assert asyncio.run(app.main.cleanup(_now() + WAITING_GAME_TTL + SECOND)) == 1000
    assert len(store) == 0 and not set(codes) & app.main.locks.keys()
    assert "Städning: 1000 spel borttagna, 0 kvar" in caplog.text


def test_cleanup_loop_survives_error(monkeypatch):
    store = GameStore()
    monkeypatch.setattr(app.main, "store", store)
    monkeypatch.setattr(app.main, "CLEANUP_INTERVAL", 0)
    game = store.create()
    game.status = "finished"
    game.last_activity -= FINISHED_GAME_TTL + SECOND
    real, calls = store.stale, []

    def flaky(now):
        calls.append(now)
        if len(calls) == 1:
            raise RuntimeError("första omgången kraschar")
        return real(now)

    monkeypatch.setattr(store, "stale", flaky)

    async def run():
        task = asyncio.create_task(app.main._cleanup_loop())
        while store.get(game.lobby_code):
            await asyncio.sleep(0)
        task.cancel()

    asyncio.run(asyncio.wait_for(run(), 2))
    assert len(calls) >= 2
