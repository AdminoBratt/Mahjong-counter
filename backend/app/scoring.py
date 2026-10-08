"""Poängberäkning för en spelare i en rond. Regler: docs/spelregler.md."""

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.store import Wind

WIND_NUMBER = {"east": 1, "south": 2, "west": 3, "north": 4}

TileNumber = Annotated[int, Field(ge=1, le=4)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Set(Strict):
    size: Literal[3, 4]  # 3tal / 4tal
    concealed: bool  # på hand / på bordet
    major: bool  # 1, 9, vind, drake / 2-8


class MahjongInput(Strict):
    from_wall: bool = False
    only_possible_tile: bool = False
    loose_tile: bool = False
    robbed_kong: bool = False
    only_majors: bool = False
    one_suit: bool = False
    two_dragons_pair: bool = False


class ScoreInput(Strict):
    chows: Annotated[int, Field(ge=0)] = 0
    sets: list[Set] = []
    scoring_pair: bool = False
    flowers: list[TileNumber] = []
    seasons: list[TileNumber] = []
    dragon_sets: Annotated[int, Field(ge=0, le=3)] = 0
    round_wind_sets: Annotated[int, Field(ge=0, le=1)] = 0
    own_wind_sets: Annotated[int, Field(ge=0, le=1)] = 0
    mahjong: MahjongInput | None = None


@dataclass
class Score:
    base_points: int
    doublings: int
    final_points: int


def score(raw: dict, seat_wind: Wind, round_wind: Wind) -> Score:
    """Räknar poäng från rådata. Kastar ValueError vid ogiltig inmatning."""
    s = ScoreInput.model_validate(raw)
    m = s.mahjong
    _check(s, seat_wind, round_wind)

    base = sum(2 * (2 if t.major else 1) * (2 if t.concealed else 1) * (4 if t.size == 4 else 1) for t in s.sets)
    base += 2 * s.scoring_pair + 4 * (len(s.flowers) + len(s.seasons))

    own = WIND_NUMBER[seat_wind]
    doublings = s.dragon_sets + s.round_wind_sets + s.own_wind_sets
    doublings += (own in s.flowers) + (own in s.seasons)
    doublings += 3 * (len(s.flowers) == 4) + 3 * (len(s.seasons) == 4)

    if m:
        drawn = m.from_wall or m.loose_tile  # lös bricka räknas också som dragning
        all_chows = s.chows == 4 and not s.scoring_pair
        base += 20 + 2 * drawn + 2 * m.only_possible_tile + 10 * m.loose_tile + 10 * m.robbed_kong + 10 * all_chows
        doublings += drawn + (s.chows == 0) + m.only_majors + 3 * m.one_suit + 3 * m.two_dragons_pair

    return Score(base, doublings, base * 2**doublings)


def _check(s: ScoreInput, seat_wind: Wind, round_wind: Wind) -> None:
    groups = s.chows + len(s.sets)
    if s.mahjong and groups != 4:
        raise ValueError("Mahjong kräver exakt fyra grupper")
    if groups > 4:
        raise ValueError("Högst fyra grupper")
    for tiles in (s.flowers, s.seasons):
        if len(set(tiles)) != len(tiles):
            raise ValueError("Samma blomma/årstid flera gånger")

    majors = sum(t.major for t in s.sets)
    if seat_wind == round_wind:
        # Samma 3tal räknas både som rondens och egen vind.
        if s.round_wind_sets != s.own_wind_sets:
            raise ValueError("Rondens vind och egen vind är samma vind")
        wind_sets = s.round_wind_sets
    else:
        wind_sets = s.round_wind_sets + s.own_wind_sets
    if s.dragon_sets + wind_sets > majors:
        raise ValueError("Fler drak-/vind-3tal än 3tal i 1,9,vind,drake")

    m = s.mahjong
    if not m:
        return
    if m.robbed_kong and (m.from_wall or m.loose_tile):
        raise ValueError("Sprängt 4tal kan inte kombineras med dragning eller lös bricka")
    if m.only_majors and (s.chows or majors != len(s.sets)):
        raise ValueError("Enbart 1or/9or/drakar/vindar men handen har annat")
    if m.two_dragons_pair and (s.dragon_sets < 2 or not s.scoring_pair):
        raise ValueError("Två drakar + par kräver två drak-3tal och poänggivande par")
