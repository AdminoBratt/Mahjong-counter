import asyncio
import os
import uuid
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, StrictBool, StringConstraints, ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.store import Game, GameError, GameStore, Round, Wind

app = FastAPI(title="Mahjong Score Tracker")
store = GameStore()
# Öppna sockets per lobby: lobbykod -> spelar-id -> socket.
connections: dict[str, dict[uuid.UUID, WebSocket]] = {}
# Ett lås per lobby runt "ändra state + skicka", så att broadcasts inte flätas ihop
# och en klient får ett gammalt lobby_update sist.
# ponytail: släpps först när spelet städas bort (4.5); ett Lock per lobby är försumbart.
locks: dict[str, asyncio.Lock] = {}
JOIN_TIMEOUT = 10  # sekunder att skicka join_lobby efter anslutning
SEND_TIMEOUT = 3  # sekunder per sändning, sedan räknas socketen som död

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
    type: Literal["submit_score"]
    round_id: uuid.UUID
    score_input: dict
    draw: StrictBool = False


async def _close(ws: WebSocket) -> None:
    try:
        await asyncio.wait_for(ws.close(), SEND_TIMEOUT)
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
    rnd = game.rounds[-1] if game.rounds else None
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
                    "score_input": s.score_input,
                    "base_points": s.base_points,
                    "doublings": s.doublings,
                    "final_points": s.final_points,
                }
                for s in rnd.scores
            },
        },
    }


def _round_complete_msg(game: Game, rnd: Round) -> dict:
    """Skickas efter att ronden avslutats, så spelarnas vindar är redan nästa ronds."""
    return {
        "type": "round_complete",
        "round_id": str(rnd.id),
        "round_number": rnd.round_number,
        "winner_id": rnd.winner_id and str(rnd.winner_id),
        "payments": {
            str(s.game_player_id): {
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
        lobby = connections.setdefault(game.lobby_code, {})
        old = lobby.get(player.id)
        lobby[player.id] = ws
        player.connected = True
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
            if kind not in ("choose_wind", "submit_score"):
                continue  # okänd typ ignoreras
            async with lock:
                if kind == "choose_wind":
                    try:
                        msg = ChooseWind.model_validate(raw)
                    except ValidationError:
                        continue
                    store.choose_wind(game, player, msg.wind)
                    # Även vid nekat val, så att den som förlorade en kapplöpning synkas om.
                    await _broadcast(game, _lobby_msg(game))
                    continue
                try:
                    msg = SubmitScore.model_validate(raw)
                    rnd = store.submit_score(game, player, msg.round_id, msg.score_input, msg.draw)
                except ValidationError:
                    await _send(ws, _error_msg("invalid_message", "Ogiltigt submit_score"))
                    continue
                except GameError as e:  # bara till avsändaren, socketen lever vidare
                    await _send(ws, _error_msg(e.code, str(e)))
                    continue
                if rnd is not None:  # round_complete före nästa ronds lobby_update
                    await _broadcast(game, _round_complete_msg(game, rnd))
                await _broadcast(game, _lobby_msg(game))
    except (WebSocketDisconnect, RuntimeError):
        pass
    async with lock:
        if lobby.get(player.id) is ws:
            del lobby[player.id]
            player.connected = False
            if not lobby:
                connections.pop(game.lobby_code, None)
            await _broadcast(game, _lobby_msg(game))


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
