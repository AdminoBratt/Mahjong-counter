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
