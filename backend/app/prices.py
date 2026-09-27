"""The only source of prices. Other backend code calls price_at / volume_since directly, not over HTTP."""

import sqlite3
from datetime import datetime

from . import config, db

# Used only until the replay loader has put bars in SQLite, so the stubs return plausible numbers.
PLACEHOLDER_PRICES = {
    "AAPL": 255.0, "AMD": 160.0, "AMZN": 220.0, "COIN": 330.0, "GOOGL": 245.0, "HOOD": 125.0,
    "META": 740.0, "MSFT": 505.0, "MSTR": 330.0, "NFLX": 1200.0, "NVDA": 178.0, "PLTR": 180.0,
    "QQQ": 595.0, "SPY": 660.0, "TSLA": 425.0, "AKAM": 116.0, "DDOG": 140.0, "INTC": 34.0, "ZS": 290.0,
}


def _conn(conn: sqlite3.Connection | None) -> sqlite3.Connection:
    return conn or db.get()


def prev_close(symbol: str, conn: sqlite3.Connection | None = None) -> float:
    """Close of the session before the replay day."""
    row = _conn(conn).execute(
        "SELECT close FROM daily_bars WHERE symbol = ? AND date < ? ORDER BY date DESC LIMIT 1",
        (symbol, config.REPLAY_DATE.isoformat()),
    ).fetchone()
    return row["close"] if row else PLACEHOLDER_PRICES[symbol]


def price_at(symbol: str, sim_time: datetime, conn: sqlite3.Connection | None = None) -> float:
    """Close of the last bar at or before sim_time.

    Before the day's first bar this is the previous session's close; after the last bar it's the last
    close, which also carries the price forward over empty minutes.
    """
    row = _conn(conn).execute(
        "SELECT close FROM bars WHERE symbol = ? AND ts <= ? ORDER BY ts DESC LIMIT 1",
        (symbol, config.iso(sim_time)),
    ).fetchone()
    return row["close"] if row else prev_close(symbol, conn)


def volume_since(symbol: str, start: datetime, sim_time: datetime, conn: sqlite3.Connection | None = None) -> int:
    """Summed bar volume with start <= ts <= sim_time, for the relative-volume rule."""
    row = _conn(conn).execute(
        "SELECT COALESCE(SUM(volume), 0) AS v FROM bars WHERE symbol = ? AND ts >= ? AND ts <= ?",
        (symbol, config.iso(start), config.iso(sim_time)),
    ).fetchone()
    return int(row["v"])


def quote(symbol: str, sim_time: datetime, conn: sqlite3.Connection | None = None) -> dict:
    """One row of GET /prices."""
    price = price_at(symbol, sim_time, conn)
    prev = prev_close(symbol, conn)
    return {
        "symbol": symbol,
        "price": round(price, 2),
        "prev_close": round(prev, 2),
        "change_pct": round((price / prev - 1) * 100, 2) if prev else 0.0,
        "sim_time": config.iso(sim_time),
    }


def history(symbol: str, sim_time: datetime, conn: sqlite3.Connection | None = None) -> list[dict]:
    """Alpaca minute bars reached by the replay clock during the scanner window."""
    cutoff = min(sim_time.astimezone(config.ET), config.SCANNER_CLOSE)
    rows = _conn(conn).execute(
        "SELECT ts, open, high, low, close, volume FROM bars "
        "WHERE symbol = ? AND ts >= ? AND ts <= ? ORDER BY ts",
        (symbol, config.iso(config.PREMARKET_OPEN), config.iso(cutoff)),
    ).fetchall()
    return [
        {
            "time": row["ts"],
            "open": round(row["open"], 4) if row["open"] is not None else round(row["close"], 4),
            "high": round(row["high"], 4) if row["high"] is not None else round(row["close"], 4),
            "low": round(row["low"], 4) if row["low"] is not None else round(row["close"], 4),
            "close": round(row["close"], 4),
            "volume": row["volume"],
        }
        for row in rows
    ]
