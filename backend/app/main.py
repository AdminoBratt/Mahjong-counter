import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
