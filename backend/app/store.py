import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

# Utan 0/O/1/I så att koden går att skriva av utan förväxling.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _now() -> datetime:
    return datetime.now(timezone.utc)


MAX_PLAYERS = 4


@dataclass
class GamePlayer:
    nickname: str
    seat_order: int  # 1-4, i den ordning spelarna gick med
    id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass
class Game:
    lobby_code: str
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    status: Literal["waiting", "active", "finished"] = "waiting"
    created_at: datetime = field(default_factory=_now)
    last_activity: datetime = field(default_factory=_now)
    players: list[GamePlayer] = field(default_factory=list)


class GameStore:
    """Alla spel i minnet, nyckel = lobbykod. Försvinner vid omstart."""

    def __init__(self) -> None:
        self._games: dict[str, Game] = {}

    def create(self) -> Game:
        # Ingen await här: anropat från en async-route körs detta atomiskt
        # på event-loopen, så två samtidiga anrop kan inte få samma kod.
        while True:
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
            if code not in self._games:
                break
        game = Game(lobby_code=code)
        self.add(game)
        return game

    def join(self, lobby_code: str, nickname: str) -> tuple[Game, GamePlayer, bool]:
        """Returnerar (spel, spelare, rejoined). Samma smeknamn = återanslutning.

        KeyError om koden är okänd, ValueError om en ny spelare inte får plats.
        Synkron av samma skäl som create(): ingen kapplöpning om sista platsen.
        """
        game = self._games[lobby_code.upper()]
        game.last_activity = _now()
        for p in game.players:
            if p.nickname.casefold() == nickname.casefold():
                return game, p, True
        if game.status != "waiting":
            raise ValueError("Spelet har redan startat")
        if len(game.players) >= MAX_PLAYERS:
            raise ValueError("Spelet är fullt")
        player = GamePlayer(nickname=nickname, seat_order=len(game.players) + 1)
        game.players.append(player)
        return game, player, False

    def add(self, game: Game) -> None:
        self._games[game.lobby_code] = game

    def get(self, lobby_code: str) -> Game | None:
        return self._games.get(lobby_code)

    def remove(self, lobby_code: str) -> None:
        self._games.pop(lobby_code, None)
