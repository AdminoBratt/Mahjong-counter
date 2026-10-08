import asyncio
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, StrictBool, StrictInt, StringConstraints, ValidationError, model_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.store import Game, GameError, GameStore, Round, Wind, _now


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()


app = FastAPI(title="Mahjong Score Tracker", lifespan=lifespan)
store = GameStore()
# Öppna sockets per lobby: lobbykod -> spelar-id -> socket.
connections: dict[str, dict[uuid.UUID, WebSocket]] = {}
# Ett lås per lobby runt "ändra state + skicka", så att broadcasts inte flätas ihop
# och en klient får ett gammalt lobby_update sist.
# Släpps när spelet städas bort (cleanup).
locks: dict[str, asyncio.Lock] = {}
JOIN_TIMEOUT = 10  # sekunder att skicka join_lobby efter anslutning
SEND_TIMEOUT = 3  # sekunder per sändning, sedan räknas socketen som död
CLEANUP_INTERVAL = float(os.environ.get("CLEANUP_INTERVAL_SECONDS", "60"))
CLOSE_FINISHED = 4000  # stängningskod: avslutat spel borttaget
CLOSE_INACTIVE = 4001  # stängningskod: inaktivt spel borttaget
log = logging.getLogger("uvicorn.error")  # uvicorn skriver ut den på INFO

cors_origins = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/games", status_code=201)
async def create_game() -> dict[str, str]:
    return {"lobby_code": store.create().lobby_code}


# strip sker före längdkontrollen, så bara mellanslag är ogiltigt.
Nickname = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)
]


class JoinRequest(BaseModel):
    nickname: Nickname


@app.post("/api/games/{lobby_code}/join")
async def join_game(lobby_code: str, body: JoinRequest) -> dict:
    try:
        game, player, rejoined = store.join(lobby_code, body.nickname)
    except KeyError:
        raise HTTPException(404, "Okänd lobbykod")
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {
        "player_id": str(player.id),
        "lobby_code": game.lobby_code,
        "rejoined": rejoined,
        "players": [
            {"id": str(p.id), "nickname": p.nickname, "seat_order": p.seat_order}
            for p in game.players
        ],
    }


class JoinLobby(BaseModel):
    type: Literal["join_lobby"]
    lobby_code: str
    nickname: Nickname


class ChooseWind(BaseModel):
    type: Literal["choose_wind"]
    wind: Wind


class SubmitScore(BaseModel):
    """Antingen rådata (score_input) eller en slutpoäng som spelaren räknat själv (final_points + mahjong)."""

    type: Literal["submit_score"]
    round_id: uuid.UUID
    score_input: dict | None = None
    final_points: StrictInt | None = None
    mahjong: StrictBool = False  # bara med final_points; med rådata gäller score_input.mahjong
    draw: StrictBool = False

    @model_validator(mode="after")
    def _one_kind(self):
        if (self.score_input is None) == (self.final_points is None):
            raise ValueError("Exakt en av score_input och final_points")
        if self.final_points is not None and self.draw:
            raise ValueError("Oavgjort skickas med score_input")
        if self.mahjong and self.score_input is not None:
            raise ValueError("mahjong bara med final_points")
        return self


async def _close(ws: WebSocket, code: int = 1000) -> None:
    try:
        await asyncio.wait_for(ws.close(code), SEND_TIMEOUT)
    except Exception:
        pass  # redan stängd eller död


async def _send(ws: WebSocket, msg: dict) -> None:
    """Misslyckad eller för långsam sändning = död socket: stäng, dess egen handler städar upp."""
    try:
        await asyncio.wait_for(ws.send_json(msg), SEND_TIMEOUT)
    except Exception:
        await _close(ws)


def _error_msg(code: str, message: str) -> dict:
    return {"type": "error", "code": code, "message": message}


async def _error(ws: WebSocket, code: str, message: str) -> None:
    await _send(ws, _error_msg(code, message))
    await _close(ws)


async def _broadcast(game: Game, msg: dict) -> None:
    for ws in list(connections.get(game.lobby_code, {}).values()):
        await _send(ws, msg)


def _lobby_msg(game: Game) -> dict:
    finished = game.status == "finished"
    # En rond som pågick när spelet avslutades räknas inte och visas inte.
    rnd = game.rounds[-1] if game.rounds and not finished else None
    return {
        "type": "lobby_update",
        "status": game.status,
        "players": [
            {
                "id": str(p.id),
                "nickname": p.nickname,
                "seat_order": p.seat_order,
                "connected": p.connected,
                "wind": p.wind,
                "total_score": p.total_score,
            }
            for p in game.players
        ],
        "current_round": rnd and {
            "id": str(rnd.id),
            "round_number": rnd.round_number,
            "round_wind": rnd.round_wind,
            "conflict": rnd.conflict(),
            "submissions": {
                str(s.game_player_id): {
                    "draw": s.draw,
                    "mahjong": s.did_mahjong,
                    "score_input": s.score_input,
                    "base_points": s.base_points,
                    "doublings": s.doublings,
                    "final_points": s.final_points,
                }
                for s in rnd.scores
            },
        },
        "last_round": _round_result(game, game.rounds[-2]) if len(game.rounds) > 1 else None,
        "score_history": game.score_history(),
        "final_result": _final_result(game) if finished else None,
    }


def _final_result(game: Game) -> dict:
    """Slutresultatet. Samma funktion för game_over och lobby_update, så det är identiskt live och efter omladdning."""
    return {
        "rounds_played": sum(r.completed for r in game.rounds),
        "ended_by": str(game.players[0].id),  # bara skaparen (plats 1) kan avsluta
        "standings": [
            {"player_id": str(p.id), "place": place, "total_score": p.total_score}
            for place, p in game.standings()
        ],
    }


def _round_result(game: Game, rnd: Round) -> dict:
    """Senast avslutade ronden. Spelarnas vindar och totaler är redan nästa ronds,
    och ändras inte förrän nästa rond avslutas. Samma innehåll live och efter omladdning."""
    return {
        "round_id": str(rnd.id),
        "round_number": rnd.round_number,
        "round_wind": rnd.round_wind,
        "winner_id": rnd.winner_id and str(rnd.winner_id),
        "payments": {
            str(s.game_player_id): {
                "wind": s.wind,
                "base_points": s.base_points,
                "doublings": s.doublings,
                "final_points": s.final_points,
                "payment_delta": s.payment_delta,
            }
            for s in rnd.scores
        },
        "new_totals": {str(p.id): p.total_score for p in game.players},
        "next_round_winds": {str(p.id): p.wind for p in game.players},
    }


@app.websocket("/ws")
async def lobby_socket(ws: WebSocket) -> None:
    # CORS gäller inte WebSockets: neka andra sajter. Samma host (även bakom proxy)
    # eller CORS_ORIGINS släpps in. Utan Origin = inte en webbläsare, kan förfalskas ändå.
    origin = ws.headers.get("origin")
    hosts = {ws.headers.get("host"), ws.headers.get("x-forwarded-host")} - {None}
    if origin and origin not in cors_origins and urlsplit(origin).netloc not in hosts:
        await ws.close(code=1008)  # före accept → handskakningen nekas med 403
        return
    await ws.accept()
    try:
        raw = await asyncio.wait_for(ws.receive_json(), JOIN_TIMEOUT)
        msg = JoinLobby.model_validate(raw)
    except WebSocketDisconnect:
        return
    except TimeoutError:
        return await _error(ws, "invalid_message", "Inget join_lobby i tid")
    except ValueError as e:  # ogiltig JSON eller ValidationError
        if isinstance(e, ValidationError) and all(
            err["loc"][:1] == ("nickname",) for err in e.errors()
        ):
            return await _error(ws, "invalid_nickname", "Smeknamnet måste vara 1–20 tecken")
        return await _error(ws, "invalid_message", "Förväntade join_lobby")

    try:
        game, player, _ = store.join(msg.lobby_code, msg.nickname)
    except KeyError:
        return await _error(ws, "unknown_lobby", "Okänd lobbykod")
    except GameError as e:
        return await _error(ws, e.code, str(e))

    lock = locks.setdefault(game.lobby_code, asyncio.Lock())
    async with lock:
        if store.get(game.lobby_code) is not game:  # städades bort medan vi väntade på låset
            return await _error(ws, "unknown_lobby", "Okänd lobbykod")
        lobby = connections.setdefault(game.lobby_code, {})
        old = lobby.get(player.id)
        lobby[player.id] = ws
        player.connected = True
        game.disconnected_since = None
        if old is not None:  # samma spelare från ny flik/sidladdning ersätter den gamla
            await _close(old)
        await _broadcast(game, _lobby_msg(game))

    try:
        while True:
            try:
                raw = await ws.receive_json()
            # Skräp ignoreras: ogiltig JSON (ValueError),
            # binär ram (KeyError/TypeError i Starlettes receive_json).
            except (ValueError, KeyError, TypeError):
                continue
            kind = raw.get("type") if isinstance(raw, dict) else None
            if kind not in ("choose_wind", "submit_score", "end_game"):
                continue  # okänd typ ignoreras
            async with lock:
                if kind == "choose_wind":
                    if game.status == "finished":
                        continue  # ignoreras tyst, ingen omsynk behövs
                    try:
                        msg = ChooseWind.model_validate(raw)
                    except ValidationError:
                        continue
                    store.choose_wind(game, player, msg.wind)
                    # Även vid nekat val, så att den som förlorade en kapplöpning synkas om.
                    await _broadcast(game, _lobby_msg(game))
                    continue
                if kind == "end_game":
                    try:
                        store.end_game(game, player)
                    except GameError as e:
                        await _send(ws, _error_msg(e.code, str(e)))
                        continue
                    await _broadcast(game, {"type": "game_over", **_final_result(game)})
                    await _broadcast(game, _lobby_msg(game))
                    continue
                try:
                    msg = SubmitScore.model_validate(raw)
                    rnd = store.submit_score(
                        game, player, msg.round_id, msg.score_input, msg.draw, msg.final_points, msg.mahjong
                    )
                except ValidationError:
                    await _send(ws, _error_msg("invalid_message", "Ogiltigt submit_score"))
                    continue
                except GameError as e:  # bara till avsändaren, socketen lever vidare
                    await _send(ws, _error_msg(e.code, str(e)))
                    continue
                if rnd is not None:  # round_complete före nästa ronds lobby_update
                    await _broadcast(game, {"type": "round_complete", **_round_result(game, rnd)})
                await _broadcast(game, _lobby_msg(game))
    except (WebSocketDisconnect, RuntimeError):
        pass
    async with lock:
        if lobby.get(player.id) is ws:
            del lobby[player.id]
            player.connected = False
            if not lobby:
                connections.pop(game.lobby_code, None)
                game.disconnected_since = _now()
            await _broadcast(game, _lobby_msg(game))


async def cleanup(now: datetime | None = None) -> int:
    """Tar bort spel som store.is_stale pekar ut, med sockets, connections och lås. Returnerar antalet.

    Under lobbyns lås, så aldrig mitt i en inlämning. now kan sättas i tester.
    """
    now = now or _now()
    removed = 0
    for game in store.stale(now):
        code = game.lobby_code
        async with locks.setdefault(code, asyncio.Lock()):
            if not store.is_stale(game, now):
                continue  # någon återanslöt medan vi väntade på låset
            close_code = CLOSE_FINISHED if game.status == "finished" else CLOSE_INACTIVE
            lobby = connections.pop(code, {})
            for ws in list(lobby.values()):
                await _close(ws, close_code)
            lobby.clear()  # handlerns slutblock (lobby.get(player.id) is ws) blir en no-op
            store.remove(code)
            locks.pop(code, None)
            removed += 1
    if removed:
        log.info("Städning: %d spel borttagna, %d kvar", removed, len(store))
    return removed


async def _cleanup_loop() -> None:
    next_report = time.monotonic()
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        try:
            await cleanup()
        except Exception:  # en misslyckad omgång får inte döda uppgiften
            log.exception("Städningen misslyckades")
        if time.monotonic() >= next_report:
            log.info("%d spel i minnet", len(store))
            next_report = time.monotonic() + 3600


class SPAStaticFiles(StaticFiles):
    """Okända sidor (t.ex. /lobby/ABC123) får index.html, men okända /api-adresser ger 404."""

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as e:
            # scope["path"], inte path: path är OS-normaliserad (backslash på Windows).
            if e.status_code != 404 or scope["path"].startswith("/api/"):
                raise
            return await super().get_response("index.html", scope)


# Den byggda frontenden kopieras hit i Docker-imagen. Saknas lokalt, då körs Vite separat.
STATIC_DIR = Path(__file__).parent.parent / "static"
if STATIC_DIR.is_dir():
    app.mount("/", SPAStaticFiles(directory=STATIC_DIR, html=True))
