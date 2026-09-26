"""Shared SQLite schema (BUILD_SPEC.md → Architecture → Defaults).

Timestamps (`bars.ts`, `news.published_at`, `alerts.ts`, `ledger.ts`) are ISO 8601 strings with the
Eastern offset, e.g. 2026-09-25T09:31:00-04:00, so they compare correctly as text within the replay day.
`daily_bars.date` is YYYY-MM-DD. Money and quantities in `ledger` are integer base units (see config.UNITS).
"""

import sqlite3

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS bars (
    symbol TEXT NOT NULL,
    ts TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL NOT NULL,
    volume INTEGER NOT NULL,
    PRIMARY KEY (symbol, ts)
);
CREATE TABLE IF NOT EXISTS daily_bars (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    close REAL NOT NULL,
    volume INTEGER NOT NULL,
    PRIMARY KEY (symbol, date)
);
CREATE TABLE IF NOT EXISTS news (
    symbol TEXT NOT NULL,
    published_at TEXT NOT NULL,
    headline TEXT NOT NULL,
    url TEXT
);
CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    ts TEXT NOT NULL,
    price REAL NOT NULL,
    change_pct REAL NOT NULL,
    rvol REAL NOT NULL,
    rules_passed TEXT NOT NULL,  -- JSON array
    headline TEXT,
    url TEXT
);
CREATE TABLE IF NOT EXISTS ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet TEXT NOT NULL,
    ts TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('deposit', 'buy', 'sell')),
    symbol TEXT,
    qty_units INTEGER,
    price REAL,
    usd_units INTEGER NOT NULL,
    signature TEXT
);
CREATE TABLE IF NOT EXISTS latest_stock_prices (
    symbol VARCHAR(5) NOT NULL,
    high FLOAT NOT NULL,
    low FLOAT NOT NULL,
    open FLOAT NOT NULL,
    close FLOAT NOT NULL,
    volume_weighted_price FLOAT NOT NULL,
    number_of_trades INTEGER NOT NULL,
    volume INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    PRIMARY KEY (symbol)
);

CREATE INDEX IF NOT EXISTS ledger_wallet ON ledger (wallet, id);
"""


def connect(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


_conn: sqlite3.Connection | None = None


def get() -> sqlite3.Connection:
    """The process-wide connection (uvicorn runs a single worker)."""
    global _conn
    if _conn is None:
        _conn = connect()
        init(_conn)
    return _conn


def use(conn: sqlite3.Connection) -> None:
    """Swap the process-wide connection, for tests."""
    global _conn
    _conn = conn
