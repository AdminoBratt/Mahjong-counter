import asyncio
import os
import uuid
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, StringConstraints, ValidationError

from app.store import Game, GameStore, JoinError, Wind

app = FastAPI(title="Mahjong Score Tracker")
store = GameStore()
# Öppna sockets per lobby: lobbykod -> spelar-id -> socket.
connections: dict[str, dict[uuid.UUID, WebSocket]] = {}
JOIN_TIMEOUT = 10  # sekunder att skicka join_lobby efter anslutning

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/games", status_code=201)
async def create_game() -> dict[str, str]:
    return {"lobby_code": store.create().lobby_code}


# strip sker före längdkontrollen, så bara mellanslag är ogiltigt.
Nickname = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)
]


class JoinRequest(BaseModel):
    nickname: Nickname


@app.post("/games/{lobby_code}/join")
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


async def _error(ws: WebSocket, code: str, message: str) -> None:
    await ws.send_json({"type": "error", "code": code, "message": message})
    await ws.close()


async def _broadcast_lobby(game: Game) -> None:
    msg = {
        "type": "lobby_update",
        "status": game.status,
        "players": [
            {
                "id": str(p.id),
                "nickname": p.nickname,
                "seat_order": p.seat_order,
                "connected": p.connected,
                "wind": p.wind,
            }
            for p in game.players
        ],
    }
    for ws in list(connections.get(game.lobby_code, {}).values()):
        try:
            await ws.send_json(msg)
        except Exception:
            pass  # död socket, dess egen handler städar upp


@app.websocket("/ws")
async def lobby_socket(ws: WebSocket) -> None:
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
    except JoinError as e:
        return await _error(ws, e.code, str(e))

    lobby = connections.setdefault(game.lobby_code, {})
    old = lobby.get(player.id)
    lobby[player.id] = ws
    player.connected = True
    if old is not None:  # samma spelare från ny flik/sidladdning ersätter den gamla
        try:
            await old.close()
        except RuntimeError:
            pass  # redan stängd
    await _broadcast_lobby(game)

    try:
        while True:
            try:
                msg = ChooseWind.model_validate(await ws.receive_json())
            # Skräp ignoreras: ogiltig JSON/ValidationError (ValueError),
            # binär ram (KeyError/TypeError i Starlettes receive_json).
            except (ValueError, KeyError, TypeError):
                continue
            store.choose_wind(game, player, msg.wind)
            # Även vid nekat val, så att den som förlorade en kapplöpning synkas om.
            await _broadcast_lobby(game)
    except (WebSocketDisconnect, RuntimeError):
        pass
    if lobby.get(player.id) is ws:
        del lobby[player.id]
        player.connected = False
        if not lobby:
            connections.pop(game.lobby_code, None)
        await _broadcast_lobby(game)
