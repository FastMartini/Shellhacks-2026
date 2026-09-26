"""Price service + replay clock (Khalil). BUILD_SPEC.md → Interface contracts → 1."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from .. import config, db, prices
from ..errors import ApiError
from ..replay import clock

router = APIRouter()


class ReplayControl(BaseModel):
    action: Literal["start", "pause", "seek"]
    speed: float | None = None
    to: datetime | None = None


@router.get("/replay/state")
def replay_state():
    return clock.state()


@router.post("/replay/control")
def replay_control(body: ReplayControl):
    if body.speed is not None:
        clock.set_speed(body.speed)
    if body.action == "start":
        clock.start()
    elif body.action == "pause":
        clock.pause()
    else:
        if body.to is None:
            raise ApiError(400, "missing_to", "seek needs a 'to' time")
        if body.to.tzinfo is None:
            raise ApiError(400, "missing_offset", "'to' needs a UTC offset, e.g. 2026-09-25T09:31:00-04:00")
        clock.seek(body.to)
    return clock.state()


@router.post("/replay/next-alert")
def replay_next_alert():
    row = db.get().execute(
        "SELECT ts FROM alerts WHERE ts > ? ORDER BY ts LIMIT 1", (config.iso(clock.sim_time),)
    ).fetchone()
    if row is None:
        raise ApiError(404, "no_next_alert", "There are no more alerts today")
    clock.seek(datetime.fromisoformat(row["ts"]))
    return clock.state()


@router.get("/prices")
def all_prices():
    t = clock.sim_time
    return [prices.quote(s, t) for s in config.SYMBOLS]


@router.get("/prices/{symbol}")
def one_price(symbol: str):
    symbol = symbol.upper()
    if symbol not in config.SYMBOLS:
        raise ApiError(404, "unknown_symbol", f"{symbol} isn't one of the 19 supported stocks")
    return prices.quote(symbol, clock.sim_time)
