"""FastAPI entry point. Run from backend/ with a single worker: uvicorn app.main:app --reload"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config, db, errors
from .routers import alerts, portfolio, replay, vault


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.get()  # opens SQLite and creates the shared schema
    yield


app = FastAPI(title="ShellHacks 2026", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)
errors.install(app)

for r in (replay.router, alerts.router, vault.router, portfolio.router):
    app.include_router(r)


@app.get("/health")
def health():
    return {"ok": True}
