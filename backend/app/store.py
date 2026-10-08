import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from pydantic import ValidationError

from app.scoring import Wind, rotate_winds, score, settle

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
    connected: bool = False  # har en öppen WebSocket just nu
    wind: Wind | None = None  # aktuell vind, None tills startvinden är vald
    total_score: int = 0


@dataclass
class RoundScore:
    game_player_id: uuid.UUID
    # None i base_points, doublings och score_input = slutpoängen angiven direkt av spelaren.
    base_points: int | None
    doublings: int | None
    final_points: int
    did_mahjong: bool
    draw: bool  # spelaren har valt oavgjort
    score_input: dict | None  # rådata från spelaren
    wind: Wind  # spelarens vind i ronden; GamePlayer.wind har roterats när ronden avslutats
    payment_delta: int = 0  # sätts när ronden avslutas


@dataclass
class Round:
    round_number: int
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    # Rondens vind roterar inte ännu, se "Känd teknisk skuld" i CLAUDE.md.
    round_wind: Wind = "east"
    is_draw: bool = False
    winner_id: uuid.UUID | None = None
    scores: list[RoundScore] = field(default_factory=list)

    def conflict(self) -> str | None:
        """Varför ronden inte kan avslutas trots att alla fyra lämnat in, annars None."""
        if len(self.scores) < MAX_PLAYERS:
            return None
        winners = sum(s.did_mahjong for s in self.scores)
        draws = sum(s.draw for s in self.scores)
        if draws == MAX_PLAYERS or (winners == 1 and not draws):
            return None
        if winners > 1:
            return "multiple_mahjong"
        if draws:
            return "draw_disagreement"
        return "no_mahjong"


@dataclass
class Game:
    lobby_code: str
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    status: Literal["waiting", "active", "finished"] = "waiting"
    created_at: datetime = field(default_factory=_now)
    last_activity: datetime = field(default_factory=_now)
    players: list[GamePlayer] = field(default_factory=list)
    rounds: list[Round] = field(default_factory=list)  # sista = aktuell rond

    def score_history(self) -> dict[str, list[int]]:
        """Total per spelare efter varje avslutad rond. Index = rondnummer, [0] = start (Beslut 55)."""
        totals = {p.id: 0 for p in self.players}
        history = {str(p.id): [0] for p in self.players}
        for rnd in self.rounds:
            if rnd.winner_id is None and not rnd.is_draw:
                continue  # pågående rond
            for s in rnd.scores:
                totals[s.game_player_id] += s.payment_delta
            for p in self.players:
                history[str(p.id)].append(totals[p.id])
        return history


class GameError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


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

        KeyError om koden är okänd, GameError om en ny spelare inte får plats.
        Synkron av samma skäl som create(): ingen kapplöpning om sista platsen.
        """
        game = self._games[lobby_code.upper()]
        game.last_activity = _now()
        for p in game.players:
            if p.nickname.casefold() == nickname.casefold():
                return game, p, True
        if game.status != "waiting":
            raise GameError("game_started", "Spelet har redan startat")
        if len(game.players) >= MAX_PLAYERS:
            raise GameError("game_full", "Spelet är fullt")
        player = GamePlayer(nickname=nickname, seat_order=len(game.players) + 1)
        game.players.append(player)
        return game, player, False

    def choose_wind(self, game: Game, player: GamePlayer, wind: Wind) -> bool:
        """Sätter spelarens startvind. False (ingen ändring) om valet inte är tillåtet.

        Spelet startar när alla fyra har valt; vindarna är unika, så alla fyra täcks.
        Synkron av samma skäl som join(): två spelare kan inte få samma vind.
        """
        if game.status != "waiting" or len(game.players) < MAX_PLAYERS:
            return False
        if any(p.wind == wind for p in game.players if p is not player):
            return False
        player.wind = wind
        game.last_activity = _now()
        if all(p.wind for p in game.players):
            game.status = "active"
            game.rounds.append(Round(round_number=1))
        return True

    def submit_score(
        self,
        game: Game,
        player: GamePlayer,
        round_id: uuid.UUID,
        raw: dict | None,
        draw: bool,
        final_points: int | None = None,
        mahjong: bool = False,
    ) -> Round | None:
        """Sparar spelarens inlämning; en ny ersätter den förra. Returnerar ronden om den avslutades.

        Antingen rådata (raw) eller en slutpoäng som spelaren räknat själv (raw=None, final_points, mahjong).
        GameError vid fel. Synkron av samma skäl som join(): ronden avslutas bara en gång.
        """
        if game.status != "active":
            raise GameError("not_active", "Spelet är inte igång")
        rnd = game.rounds[-1]
        if round_id != rnd.id:
            raise GameError("wrong_round", "Ronden är redan avslutad eller okänd")
        if raw is None:
            # Beslut 45-47: backend räknar inte om en direkt slutpoäng, bara rimlighetskontroll.
            if final_points < 0:
                raise GameError("invalid_score", "Slutpoängen kan inte vara negativ")
            if final_points % 2:
                raise GameError("invalid_score", "Slutpoängen är alltid ett jämnt tal")
            if mahjong and final_points < 20:
                raise GameError("invalid_score", "Mahjong ger minst 20 poäng")
            base_points = doublings = None
            did_mahjong = mahjong
        else:
            try:
                s = score(raw, player.wind, rnd.round_wind)
            except ValueError as e:
                msg = "Ogiltig poänginmatning" if isinstance(e, ValidationError) else str(e)
                raise GameError("invalid_score", msg) from e
            base_points, doublings, final_points = s.base_points, s.doublings, s.final_points
            did_mahjong = raw.get("mahjong") is not None  # raw är en giltig dict efter score()
        if draw and did_mahjong:
            raise GameError("invalid_score", "Oavgjort och Mahjong samtidigt")

        rnd.scores = [x for x in rnd.scores if x.game_player_id != player.id]
        rnd.scores.append(
            RoundScore(player.id, base_points, doublings, final_points, did_mahjong, draw, raw, player.wind)
        )
        game.last_activity = _now()
        if len(rnd.scores) < MAX_PLAYERS or rnd.conflict():
            return None

        win = next((x for x in rnd.scores if x.did_mahjong), None)  # None = alla valde oavgjort
        winner = str(win.game_player_id) if win else None
        east = next(str(p.id) for p in game.players if p.wind == "east")
        deltas = settle({str(x.game_player_id): x.final_points for x in rnd.scores}, winner, east)
        winds = rotate_winds({str(p.id): p.wind for p in game.players}, winner)
        for x in rnd.scores:
            x.payment_delta = deltas[str(x.game_player_id)]
        for p in game.players:
            p.total_score += deltas[str(p.id)]
            p.wind = winds[str(p.id)]
        rnd.is_draw = win is None
        rnd.winner_id = win.game_player_id if win else None
        game.rounds.append(Round(round_number=rnd.round_number + 1))
        return rnd

    def add(self, game: Game) -> None:
        self._games[game.lobby_code] = game

    def get(self, lobby_code: str) -> Game | None:
        return self._games.get(lobby_code)

    def remove(self, lobby_code: str) -> None:
        self._games.pop(lobby_code, None)
