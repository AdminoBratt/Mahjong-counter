import os
from typing import Annotated

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, StringConstraints

from app.store import GameStore

app = FastAPI(title="Mahjong Score Tracker")
store = GameStore()

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


class JoinRequest(BaseModel):
    # strip sker före längdkontrollen, så bara mellanslag ger 422.
    nickname: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)
    ]


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
