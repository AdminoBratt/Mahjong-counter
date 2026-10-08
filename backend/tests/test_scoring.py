import pytest

from app.scoring import rotate_winds, score, settle


def pong(major=False, concealed=False, size=3):
    return {"size": size, "concealed": concealed, "major": major}


# Vinnarhand utan bonusar: 3 följder + ett 3tal 2-8 på bordet = 20 + 2.
WIN = {"chows": 3, "sets": [pong()], "mahjong": {}}


def calc(raw, seat="south", round_wind="east"):
    s = score(raw, seat, round_wind)
    assert s.final_points == s.base_points * 2**s.doublings
    return s.base_points, s.doublings


@pytest.mark.parametrize(
    "raw, expected",
    [
        ({"chows": 1}, 0),  # 3-följd
        ({"sets": [pong()]}, 2),
        ({"sets": [pong(major=True)]}, 4),
        ({"sets": [pong(concealed=True)]}, 4),
        ({"sets": [pong(major=True, concealed=True)]}, 8),
        ({"sets": [pong(size=4)]}, 8),
        ({"sets": [pong(major=True, size=4)]}, 16),
        ({"sets": [pong(concealed=True, size=4)]}, 16),
        ({"sets": [pong(major=True, concealed=True, size=4)]}, 32),
        ({"scoring_pair": True}, 2),
        ({"flowers": [1], "seasons": [3]}, 8),  # 4p per st, ingen egen (Syd=2)
    ],
)
def test_combinations(raw, expected):
    assert calc(raw) == (expected, 0)


@pytest.mark.parametrize(
    "raw, expected",
    [
        (WIN, (22, 0)),  # gjort Mahjong: 20 + 3talets 2
        ({**WIN, "mahjong": {"from_wall": True}}, (24, 1)),
        ({**WIN, "mahjong": {"only_possible_tile": True}}, (24, 0)),
        ({**WIN, "mahjong": {"loose_tile": True}}, (34, 1)),  # 10p + räknas som dragning
        ({**WIN, "mahjong": {"robbed_kong": True}}, (32, 0)),
        ({"chows": 4, "mahjong": {}}, (30, 0)),  # bara följder
    ],
)
def test_mahjong_bonuses(raw, expected):
    assert calc(raw) == expected


def test_only_chows_needs_non_scoring_pair():
    assert calc({"chows": 4, "scoring_pair": True, "mahjong": {}}) == (22, 0)


def test_loose_tile_and_from_wall_count_drawn_once():
    assert calc({**WIN, "mahjong": {"loose_tile": True, "from_wall": True}}) == (34, 1)


@pytest.mark.parametrize(
    "raw, seat, expected",
    [
        ({"sets": [pong(major=True)], "dragon_sets": 1}, "south", 1),
        ({"sets": [pong(major=True)], "round_wind_sets": 1}, "south", 1),
        ({"sets": [pong(major=True)], "own_wind_sets": 1}, "south", 1),
        ({"sets": [pong(major=True)], "round_wind_sets": 1, "own_wind_sets": 1}, "east", 2),
        ({"flowers": [2], "seasons": [2]}, "south", 2),  # egen blomma + egen årstid
        ({"flowers": [1, 2, 3, 4]}, "south", 4),  # alla 4 blommor 3× + egen 1×
        ({"seasons": [1, 2, 3, 4]}, "south", 4),
        ({"flowers": [1, 2, 3, 4], "seasons": [1, 2, 3, 4]}, "south", 8),  # 6× + egna 2×
    ],
)
def test_general_doublings(raw, seat, expected):
    assert score(raw, seat, "east").doublings == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ({**WIN, "mahjong": {"from_wall": True}}, 1),
        ({"sets": [pong()] * 4, "mahjong": {}}, 1),  # ingen följd
        ({"sets": [pong(major=True)] * 4, "mahjong": {"only_majors": True}}, 2),  # + ingen följd
        ({**WIN, "mahjong": {"one_suit": True}}, 3),
        (
            {
                "chows": 2,
                "sets": [pong(major=True)] * 2,
                "dragon_sets": 2,
                "scoring_pair": True,
                "mahjong": {"two_dragons_pair": True},
            },
            5,  # 3× + 1× per drak-3tal
        ),
    ],
)
def test_mahjong_doublings(raw, expected):
    assert calc(raw)[1] == expected


def test_full_hand():
    raw = {
        "chows": 1,
        "sets": [pong(major=True, concealed=True, size=4), pong(), pong(major=True)],
        "scoring_pair": True,
        "flowers": [2],
        "dragon_sets": 1,
        "round_wind_sets": 1,
        "mahjong": {"from_wall": True},
    }
    s = score(raw, "south", "east")
    assert (s.base_points, s.doublings, s.final_points) == (66, 4, 1056)


@pytest.mark.parametrize(
    "raw, seat",
    [
        ({"bogus": 1}, "south"),
        ({"chows": -1}, "south"),
        ({"chows": "1"}, "south"),
        ({"flowers": [5]}, "south"),
        ({"flowers": [1, 1]}, "south"),
        ({"flowers": [1, 2, 3, 4, 1]}, "south"),
        ({"chows": 5}, "south"),
        ({"chows": 3, "mahjong": {}}, "south"),  # vinnaren behöver exakt 4 grupper
        ({"from_wall": True}, "south"),  # Mahjong-bonus utan Mahjong
        ({"dragon_sets": 4}, "south"),
        ({"own_wind_sets": 2}, "south"),
        ({"sets": [pong(major=True)], "dragon_sets": 1, "own_wind_sets": 1}, "south"),
        ({"sets": [pong(major=True)], "round_wind_sets": 1}, "east"),  # samma vind, olika räknare
        ({**WIN, "mahjong": {"robbed_kong": True, "from_wall": True}}, "south"),
        ({**WIN, "mahjong": {"robbed_kong": True, "loose_tile": True}}, "south"),
        ({**WIN, "mahjong": {"only_majors": True}}, "south"),
        ({**WIN, "sets": [pong(major=True)], "dragon_sets": 1, "mahjong": {"two_dragons_pair": True}}, "south"),
        (
            {"chows": 2, "sets": [pong(major=True)] * 2, "dragon_sets": 2, "mahjong": {"two_dragons_pair": True}},
            "south",
        ),
    ],
)
def test_invalid_input(raw, seat):
    with pytest.raises(ValueError):
        score(raw, seat, "east")


def pay(points, winner, east="Ö"):
    delta = settle(points, winner, east)
    assert sum(delta.values()) == 0
    return delta


@pytest.mark.parametrize(
    "points, winner, expected",
    [
        # Exemplet i spelregler.md: Nordan vinner.
        ({"N": 48, "Ö": 24, "S": 8, "V": 32}, "N", {"N": 192, "Ö": -80, "V": -8, "S": -104}),
        # Öst vinner: alla betalar dubbelt, förlorarna gör upp utan dubblering.
        ({"Ö": 10, "S": 4, "V": 6, "N": 2}, "Ö", {"Ö": 60, "S": -20, "V": -14, "N": -26}),
        # Vanlig förlorare vinner.
        ({"S": 10, "Ö": 6, "V": 4, "N": 2}, "S", {"S": 40, "Ö": -8, "V": -12, "N": -20}),
        # Två lika förlorare utan Öst.
        ({"N": 10, "Ö": 2, "S": 6, "V": 6}, "N", {"N": 40, "Ö": -36, "S": -2, "V": -2}),
        # Två lika förlorare där den ena är Öst.
        ({"N": 10, "Ö": 6, "S": 6, "V": 2}, "N", {"N": 40, "Ö": -12, "S": -6, "V": -22}),
        # Förlorare (V) med fler poäng än vinnaren betalar ändå vinnarens poäng.
        ({"S": 4, "Ö": 2, "V": 10, "N": 0}, "S", {"S": 16, "Ö": -20, "V": 22, "N": -18}),
        # Oavgjort: inga betalningar.
        ({"N": 48, "Ö": 24, "S": 8, "V": 32}, None, {"N": 0, "Ö": 0, "S": 0, "V": 0}),
    ],
)
def test_settle(points, winner, expected):
    assert pay(points, winner) == expected


@pytest.mark.parametrize("east", ["Ö", "S", "V", "N"])
@pytest.mark.parametrize("winner", ["Ö", "S", "V", "N", None])
def test_settle_all_winners_and_easts(winner, east):
    delta = pay({"Ö": 24, "S": 8, "V": 32, "N": 48}, winner, east)
    assert all(type(d) is int for d in delta.values())
    if winner:
        assert delta[winner] >= 0


@pytest.mark.parametrize(
    "points, winner, east",
    [
        ({"Ö": 1, "S": 1, "V": 1}, "Ö", "Ö"),
        ({"Ö": 1, "S": 1, "V": 1, "N": 1, "X": 1}, "Ö", "Ö"),
        ({"Ö": 1, "S": 1, "V": 1, "N": 1}, "X", "Ö"),
        ({"Ö": 1, "S": 1, "V": 1, "N": 1}, "Ö", "X"),
        ({"Ö": 1, "S": -1, "V": 1, "N": 1}, "Ö", "Ö"),
        ({"Ö": 1, "S": 1.5, "V": 1, "N": 1}, "Ö", "Ö"),
        ({"Ö": 1, "S": True, "V": 1, "N": 1}, "Ö", "Ö"),
    ],
)
def test_settle_invalid_input(points, winner, east):
    with pytest.raises(ValueError):
        settle(points, winner, east)


START = {"A": "east", "B": "south", "C": "west", "D": "north"}


def rotate(winds, winner):
    before = dict(winds)
    after = rotate_winds(winds, winner)
    assert winds == before  # indatat muteras inte
    assert after.keys() == winds.keys()
    assert sorted(after.values()) == sorted(START.values())  # varje vind exakt en gång
    return after


def test_rotate_winds():
    assert rotate(START, "B") == {"A": "north", "B": "east", "C": "south", "D": "west"}


@pytest.mark.parametrize(
    "winner, expected",
    [
        ("A", START),
        ("B", {"A": "north", "B": "east", "C": "south", "D": "west"}),
        ("C", {"A": "north", "B": "east", "C": "south", "D": "west"}),
        ("D", {"A": "north", "B": "east", "C": "south", "D": "west"}),
    ],
)
def test_rotate_winds_each_winner(winner, expected):
    assert rotate(START, winner) == expected


def test_rotate_winds_four_rotations_back_to_start():
    winds = START
    for _ in range(4):
        non_east = next(p for p, w in winds.items() if w != "east")
        winds = rotate(winds, non_east)
    assert winds == START


def test_rotate_winds_east_wins_or_draw_unchanged():
    assert rotate(START, "A") == START
    assert rotate(START, None) == START


def test_rotate_winds_new_east_wins():
    winds = rotate(START, "C")  # B blir Öst
    assert winds["B"] == "east"
    assert rotate(winds, "B") == winds


def test_rotate_winds_hand_example():
    # Exemplet i planen: B vann rond 1, A vann rond 2, oavgjort rond 3, C (Öst) vann rond 4.
    r2 = rotate(START, "B")
    r3 = rotate(r2, "A")
    assert r3 == {"A": "west", "B": "north", "C": "east", "D": "south"}
    assert rotate(r3, None) == r3
    assert rotate(r3, "C") == r3


@pytest.mark.parametrize(
    "winds, winner",
    [
        ({"A": "east", "B": "south", "C": "west"}, "A"),
        ({**START, "E": "east"}, "A"),
        ({**START, "D": "east"}, "A"),
        ({**START, "D": "up"}, "A"),
        (START, "X"),
    ],
)
def test_rotate_winds_invalid_input(winds, winner):
    with pytest.raises(ValueError):
        rotate_winds(winds, winner)
