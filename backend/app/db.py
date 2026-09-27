"""Shared SQLite schema (BUILD_SPEC.md → Architecture → Defaults).

Timestamps (`bars.ts`, `news.published_at`, `news_triggers.ts`, `alerts.ts`, `ledger.ts`) are ISO 8601 strings with the
Eastern offset, e.g. 2026-09-25T09:31:00-04:00, so they compare correctly as text within the replay day.
`daily_bars.date` is YYYY-MM-DD. Money and quantities in `ledger` are integer base units (see config.UNITS).
"""

import sqlite3
import threading

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
CREATE TABLE IF NOT EXISTS news_triggers (
    symbol TEXT PRIMARY KEY,
    ts TEXT NOT NULL
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
CREATE INDEX IF NOT EXISTS ledger_wallet ON ledger (wallet, id);
"""


def connect(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


_pinned: sqlite3.Connection | None = None
_local = threading.local()


def get() -> sqlite3.Connection:
    """This thread's connection. Sync routes run in FastAPI's threadpool, and one sqlite3 connection
    shared across threads raises InterfaceError under the app's 2 s polling. WAL lets those reads run
    while the vault writes a ledger row."""
    if _pinned is not None:
        return _pinned
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = connect()
        conn.execute("PRAGMA journal_mode=WAL")
        init(conn)
        _local.conn = conn
    return conn


def use(conn: sqlite3.Connection | None) -> None:
    """Pin one connection for every thread, for tests (an in-memory DB is per connection). None unpins."""
    global _pinned, _local
    _pinned = conn
    _local = threading.local()
