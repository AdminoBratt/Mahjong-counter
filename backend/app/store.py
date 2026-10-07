import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Game:
    lobby_code: str
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    status: Literal["waiting", "active", "finished"] = "waiting"
    created_at: datetime = field(default_factory=_now)
    last_activity: datetime = field(default_factory=_now)
    players: list = field(default_factory=list)


class GameStore:
    """Alla spel i minnet, nyckel = lobbykod. Försvinner vid omstart."""

    def __init__(self) -> None:
        self._games: dict[str, Game] = {}

    def add(self, game: Game) -> None:
        self._games[game.lobby_code] = game

    def get(self, lobby_code: str) -> Game | None:
        return self._games.get(lobby_code)

    def remove(self, lobby_code: str) -> None:
        self._games.pop(lobby_code, None)
