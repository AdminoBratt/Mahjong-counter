import re

import pytest

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


def _game_with(store, *names, status="waiting"):
    game = store.create()
    for n in names:
        store.join(game.lobby_code, n)
    game.status = status
    return game


def test_join_assigns_seats_in_order():
    store = GameStore()
    game = _game_with(store, "Anna", "Bo")
    assert [(p.nickname, p.seat_order) for p in game.players] == [("Anna", 1), ("Bo", 2)]


def test_join_same_nickname_rejoins_casefolded():
    store = GameStore()
    game = _game_with(store, "Straße")
    _, player, rejoined = store.join(game.lobby_code.lower(), "STRASSE")
    assert rejoined and player is game.players[0]
    assert len(game.players) == 1


def test_join_full_game():
    store = GameStore()
    game = _game_with(store, "A", "B", "C", "D")
    with pytest.raises(ValueError):
        store.join(game.lobby_code, "E")
    assert store.join(game.lobby_code, "d") == (game, game.players[3], True)


def test_join_active_game():
    store = GameStore()
    game = _game_with(store, "A", status="active")
    with pytest.raises(ValueError):
        store.join(game.lobby_code, "B")
    assert store.join(game.lobby_code, "A") == (game, game.players[0], True)


def test_join_unknown_code():
    with pytest.raises(KeyError):
        GameStore().join("NOPE00", "A")
