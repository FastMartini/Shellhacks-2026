"""Average-cost trade log and portfolio stats, computed from ledger rows (BUILD_SPEC.md → Stats).

Pure functions: pass the wallet's ledger rows (oldest first) and a price function, so this is easy to test.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from . import config

PriceFn = Callable[[str, datetime], float]


@dataclass
class Position:
    qty_units: int = 0
    avg_cost: float = 0.0
    opened_at: datetime | None = None


def _usd(units: int) -> float:
    return round(units / config.UNITS, 2)


def _qty(units: int) -> float:
    return round(units / config.UNITS, 6)


def explorer_url(signature: str | None) -> str | None:
    return f"https://explorer.solana.com/tx/{signature}?cluster=devnet" if signature else None


class Book:
    """Replays ledger rows in order, tracking cash, deposits and average-cost positions."""

    def __init__(self):
        self.cash_units = 0
        self.deposited_units = 0
        self.positions: dict[str, Position] = {}
        self.transactions: list[dict] = []  # oldest first

    def apply(self, row) -> None:
        ts = datetime.fromisoformat(row["ts"])
        kind, units = row["kind"], row["usd_units"]
        if kind == "deposit":
            self.cash_units += units
            self.deposited_units += units
            return

        symbol, qty_units, price = row["symbol"], row["qty_units"], row["price"]
        pos = self.positions.setdefault(symbol, Position())
        cash_before = self.cash_units
        tx = {
            "id": row["id"], "sim_time": config.iso(ts), "symbol": symbol, "side": kind,
            "qty": _qty(qty_units), "price": round(price, 2), "usd_amount": _usd(units),
            "cash_before": 0.0, "cash_after": 0.0,
            "realized_pl": None, "realized_pl_pct": None, "outcome": None,
            "opened_at": None, "held_min": None,
            "signature": row["signature"], "explorer_url": explorer_url(row["signature"]),
        }

        if kind == "buy":
            self.cash_units -= units
            if pos.qty_units == 0:
                pos.opened_at = ts
            total = pos.qty_units + qty_units
            pos.avg_cost = (pos.qty_units * pos.avg_cost + qty_units * price) / total
            pos.qty_units = total
        else:
            self.cash_units += units
            realized = (price - pos.avg_cost) * qty_units / config.UNITS
            tx["realized_pl"] = round(realized, 2)
            tx["realized_pl_pct"] = round((price / pos.avg_cost - 1) * 100, 2) if pos.avg_cost else None
            tx["outcome"] = "win" if tx["realized_pl"] > 0 else "loss" if tx["realized_pl"] < 0 else None
            if pos.opened_at:
                tx["opened_at"] = config.iso(pos.opened_at)
                tx["held_min"] = int((ts - pos.opened_at).total_seconds() // 60)
            pos.qty_units = max(0, pos.qty_units - qty_units)
            if pos.qty_units == 0:
                self.positions[symbol] = Position()  # average cost resets when the position closes

        tx["cash_before"] = _usd(cash_before)
        tx["cash_after"] = _usd(self.cash_units)
        self.transactions.append(tx)

    def holdings_value(self, price_fn: PriceFn, at: datetime) -> float:
        return sum(p.qty_units / config.UNITS * price_fn(s, at) for s, p in self.positions.items() if p.qty_units)


def transactions(rows) -> list[dict]:
    """GET /transactions: buys and sells, newest first."""
    book = Book()
    for row in rows:
        book.apply(row)
    return list(reversed(book.transactions))


def transaction(rows, row_id: int) -> dict | None:
    """One /transactions row by ledger id, for /trade/submit to return after ledger.record().

    Replays the whole ledger because cash_before, realized P/L and held_min depend on earlier rows.
    None for a deposit or an unknown id.
    """
    return next((t for t in transactions(rows) if t["id"] == row_id), None)


def portfolio(rows, price_fn: PriceFn, sim_time: datetime) -> dict:
    """GET /portfolio."""
    book = Book()
    for row in rows:
        book.apply(row)

    holdings = []
    for symbol, pos in sorted(book.positions.items()):
        if not pos.qty_units:
            continue
        qty = pos.qty_units / config.UNITS
        price = price_fn(symbol, sim_time)
        holdings.append({
            "symbol": symbol, "qty": _qty(pos.qty_units), "avg_cost": round(pos.avg_cost, 2),
            "price": round(price, 2), "market_value": round(qty * price, 2),
            "unrealized_pl": round((price - pos.avg_cost) * qty, 2),
        })

    cash = book.cash_units / config.UNITS
    deposited = book.deposited_units / config.UNITS
    total_value = cash + book.holdings_value(price_fn, sim_time)
    total_pl = total_value - deposited
    sells = [t for t in book.transactions if t["side"] == "sell"]
    wins = [t["realized_pl"] for t in sells if t["outcome"] == "win"]
    losses = [t["realized_pl"] for t in sells if t["outcome"] == "loss"]

    return {
        "cash": round(cash, 2),
        "holdings": holdings,
        "total_value": round(total_value, 2),
        "deposited": round(deposited, 2),
        "stats": {
            "total_pl": round(total_pl, 2),
            "total_pl_pct": round(total_pl / deposited * 100, 2) if deposited else 0.0,
            "avg_win": round(sum(wins) / len(wins), 2) if wins else None,
            "avg_loss": round(sum(losses) / len(losses), 2) if losses else None,
            "trade_count": len(book.transactions),
            "win_count": len(wins),
            "loss_count": len(losses),
        },
        "equity_curve": equity_curve(rows, price_fn, sim_time),
    }


def equity_curve(rows, price_fn: PriceFn, sim_time: datetime) -> list[dict]:
    """Total value at every replay minute from the first ledger row up to sim_time (at most ~390 points)."""
    rows = list(rows)
    if not rows:
        return []
    t = datetime.fromisoformat(rows[0]["ts"]).replace(second=0, microsecond=0)
    book, i, points = Book(), 0, []
    while t <= sim_time:
        while i < len(rows) and datetime.fromisoformat(rows[i]["ts"]) <= t:
            book.apply(rows[i])
            i += 1
        value = book.cash_units / config.UNITS + book.holdings_value(price_fn, t)
        points.append({"t": config.iso(t), "value": round(value, 2)})
        t += timedelta(minutes=1)
    return points
