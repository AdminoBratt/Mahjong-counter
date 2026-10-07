import re

from app.store import Game, GameStore


def test_add_get_remove():
    store = GameStore()
    game = Game(lobby_code="ABC123")
    store.add(game)
    assert store.get("ABC123") is game
    store.remove("ABC123")
    assert store.get("ABC123") is None


def test_unknown_code():
    store = GameStore()
    assert store.get("NOPE00") is None
    store.remove("NOPE00")  # ingen krasch


def test_create_generates_code_and_stores_game():
    store = GameStore()
    game = store.create()
    assert re.fullmatch(r"[A-HJ-NP-Z2-9]{6}", game.lobby_code)
    assert store.get(game.lobby_code) is game


def test_create_retries_on_collision(monkeypatch):
    store = GameStore()
    store.add(Game(lobby_code="AAAAAA"))
    chars = iter("AAAAAABBBBBB")
    monkeypatch.setattr("app.store.secrets.choice", lambda _: next(chars))
    assert store.create().lobby_code == "BBBBBB"
    assert len(store._games) == 2
