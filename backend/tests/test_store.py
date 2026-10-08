import re

import pytest

from app.store import Game, GameStore, GameError


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
    with pytest.raises(GameError) as e:
        store.join(game.lobby_code, "E")
    assert e.value.code == "game_full"
    assert store.join(game.lobby_code, "d") == (game, game.players[3], True)


def test_join_active_game():
    store = GameStore()
    game = _game_with(store, "A", status="active")
    with pytest.raises(GameError) as e:
        store.join(game.lobby_code, "B")
    assert e.value.code == "game_started"
    assert store.join(game.lobby_code, "A") == (game, game.players[0], True)


def test_join_unknown_code():
    with pytest.raises(KeyError):
        GameStore().join("NOPE00", "A")


def test_choose_wind_needs_four_players():
    store = GameStore()
    game = _game_with(store, "A", "B", "C")
    assert store.choose_wind(game, game.players[0], "east") is False
    assert game.players[0].wind is None


def test_choose_wind_switch_taken_and_start():
    store = GameStore()
    game = _game_with(store, "A", "B", "C", "D")
    a, b, c, d = game.players
    assert store.choose_wind(game, a, "east")
    assert store.choose_wind(game, a, "south") and a.wind == "south"  # byte
    assert store.choose_wind(game, a, "south")  # samma igen är ok
    assert store.choose_wind(game, b, "south") is False and b.wind is None  # tagen
    for p, w in ((b, "east"), (c, "west")):
        assert store.choose_wind(game, p, w)
    assert game.status == "waiting"
    assert store.choose_wind(game, d, "north")
    assert game.status == "active"
    assert store.choose_wind(game, a, "east") is False and a.wind == "south"  # låst
    with pytest.raises(GameError) as e:
        store.join(game.lobby_code, "E")
    assert e.value.code == "game_started"


def _active_game(store):
    """A=öst, B=syd, C=väst, D=nord. Returnerar (spel, A, B, C, D)."""
    game = _game_with(store, "A", "B", "C", "D")
    for p, w in zip(game.players, ("east", "south", "west", "north")):
        store.choose_wind(game, p, w)
    return (game, *game.players)


SET_2 = {"sets": [{"size": 3, "concealed": False, "major": False}]}  # 2p
SET_4 = {"sets": [{"size": 3, "concealed": True, "major": False}]}  # 4p
CHOWS_MAHJONG = {"chows": 4, "mahjong": {}}  # 20 + 10 (bara följder) = 30p


def _submit_all(store, game, inputs, draw=False):
    """inputs: score_input per spelare i sittordning. Returnerar resultatet av sista inlämningen."""
    rid = game.rounds[-1].id
    for p, raw in zip(game.players, inputs):
        result = store.submit_score(game, p, rid, raw, draw)
    return result


def test_round_starts_when_game_becomes_active():
    store = GameStore()
    game, *_ = _active_game(store)
    assert [r.round_number for r in game.rounds] == [1]
    assert game.rounds[0].round_wind == "east"


def test_full_rounds_settle_rotate_and_sum_to_zero():
    store = GameStore()
    game, a, b, c, d = _active_game(store)
    players = game.players

    # Rond 1: Nord (D) vinner med 30p. Öst 2p, Syd 0p, Väst 4p.
    rnd = _submit_all(store, game, [SET_2, {}, SET_4, CHOWS_MAHJONG])
    assert rnd is game.rounds[0] and rnd.winner_id == d.id and not rnd.is_draw
    # D: 60 (Öst×2) + 30 + 30. Förlorare: Öst-Syd 2×2, Väst-Öst 2×2, Väst-Syd 4.
    # Öst: -60 -4 (till Väst) +4 (från Syd). Syd: -30 -4 -4. Väst: -30 +4 +4.
    assert {x.game_player_id: x.payment_delta for x in rnd.scores} == {
        a.id: -60, b.id: -38, c.id: -22, d.id: 120
    }
    assert [p.total_score for p in players] == [-60, -38, -22, 120]
    assert sum(p.total_score for p in players) == 0
    # Icke-Öst vann: moturs, Syd blir ny Öst.
    assert [p.wind for p in players] == ["north", "east", "south", "west"]
    assert [r.round_number for r in game.rounds] == [1, 2]
    assert game.rounds[1].id != rnd.id

    # Rond 2 använder de roterade vindarna: blomma 1 är nu B:s egen (Öst) → 1×.
    rnd = _submit_all(store, game, [{}, {**CHOWS_MAHJONG, "flowers": [1]}, {}, {}])
    b_score = next(x for x in rnd.scores if x.game_player_id == b.id)
    assert (b_score.base_points, b_score.doublings, b_score.final_points) == (34, 1, 68)
    # Öst vinner: alla betalar 68×2, förlorarna har lika (0p) och gör inget sinsemellan.
    assert [p.total_score for p in players] == [-60 - 136, -38 + 408, -22 - 136, 120 - 136]
    assert sum(p.total_score for p in players) == 0
    assert [p.wind for p in players] == ["north", "east", "south", "west"]  # Öst vann: står still

    # Rond 3: alla fyra väljer oavgjort. Poängen ignoreras.
    totals = [p.total_score for p in players]
    rnd = _submit_all(store, game, [SET_4, {}, {}, SET_2], draw=True)
    assert rnd.is_draw and rnd.winner_id is None
    assert all(x.payment_delta == 0 for x in rnd.scores)
    assert [p.total_score for p in players] == totals
    assert sum(totals) == 0
    assert [p.wind for p in players] == ["north", "east", "south", "west"]
    assert [r.round_number for r in game.rounds] == [1, 2, 3, 4]
    assert all(r.round_wind == "east" for r in game.rounds)


def test_resubmit_replaces_previous():
    store = GameStore()
    game, a, *_ = _active_game(store)
    rid = game.rounds[0].id
    assert store.submit_score(game, a, rid, SET_2, False) is None
    assert store.submit_score(game, a, rid, SET_4, False) is None
    [only] = game.rounds[0].scores
    assert only.final_points == 4 and only.score_input == SET_4


@pytest.mark.parametrize(
    "draws, mahjongs, code",
    [
        ("", "", "no_mahjong"),
        ("", "AB", "multiple_mahjong"),
        ("BCD", "", "draw_disagreement"),
        ("B", "A", "draw_disagreement"),
    ],
)
def test_conflicts_keep_round_open_until_resolved(draws, mahjongs, code):
    store = GameStore()
    game, *players = _active_game(store)
    rnd = game.rounds[0]
    for p in players:
        raw = CHOWS_MAHJONG if p.nickname in mahjongs else {}
        assert store.submit_score(game, p, rnd.id, raw, p.nickname in draws) is None
    assert rnd.conflict() == code
    assert len(game.rounds) == 1 and all(p.total_score == 0 for p in players)

    # Upplöses genom att resten byter till oavgjort; avslutas först vid den sista.
    *first, last = [p for p in players if p.nickname not in draws]
    for p in first:
        assert store.submit_score(game, p, rnd.id, {}, True) is None
    assert store.submit_score(game, last, rnd.id, {}, True) is rnd
    assert rnd.is_draw and len(game.rounds) == 2


def test_conflict_none_until_all_four_submitted():
    store = GameStore()
    game, a, *_ = _active_game(store)
    store.submit_score(game, a, game.rounds[0].id, {}, False)
    assert game.rounds[0].conflict() is None


@pytest.mark.parametrize(
    "raw, draw",
    [
        ({"chows": -1}, False),  # pydantic
        ({"okänt": 1}, False),  # extra fält
        ("inte en dict", False),
        ({"chows": 5}, False),  # _check: för många grupper
        (CHOWS_MAHJONG, True),  # oavgjort + Mahjong
    ],
)
def test_invalid_score(raw, draw):
    store = GameStore()
    game, a, *_ = _active_game(store)
    with pytest.raises(GameError) as e:
        store.submit_score(game, a, game.rounds[0].id, raw, draw)
    assert e.value.code == "invalid_score" and str(e.value)
    assert game.rounds[0].scores == []


def test_wrong_round_and_not_active():
    store = GameStore()
    game, a, b, c, d = _active_game(store)
    old = game.rounds[0].id
    _submit_all(store, game, [CHOWS_MAHJONG, {}, {}, {}])
    with pytest.raises(GameError) as e:
        store.submit_score(game, a, old, {}, False)
    assert e.value.code == "wrong_round"

    waiting = _game_with(store, "A")
    with pytest.raises(GameError) as e:
        store.submit_score(waiting, waiting.players[0], old, {}, False)
    assert e.value.code == "not_active"
