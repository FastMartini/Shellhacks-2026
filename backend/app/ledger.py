"""Ledger of deposits and trades (Khalil). The source of truth for cash, deposits and positions."""

from datetime import datetime

from . import config, db


def record(wallet: str, kind: str, symbol: str | None, qty_units: int | None, price: float | None,
           usd_units: int, sim_time: datetime, signature: str | None) -> int:
    """Write one ledger row; the vault calls this after a confirmed transaction. Returns the row id."""
    if kind not in ("deposit", "buy", "sell"):
        raise ValueError(f"unknown ledger kind: {kind}")
    conn = db.get()
    cur = conn.execute(
        "INSERT INTO ledger (wallet, ts, kind, symbol, qty_units, price, usd_units, signature)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (wallet, config.iso(sim_time), kind, symbol, qty_units, price, usd_units, signature),
    )
    conn.commit()
    return cur.lastrowid


def rows(wallet: str) -> list:
    """The wallet's ledger rows, oldest first."""
    return db.get().execute("SELECT * FROM ledger WHERE wallet = ? ORDER BY ts, id", (wallet,)).fetchall()


def clear(wallet: str) -> None:
    """The ledger part of /demo/reset."""
    conn = db.get()
    conn.execute("DELETE FROM ledger WHERE wallet = ?", (wallet,))
    conn.commit()
