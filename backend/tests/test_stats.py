from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import config, db, ledger, stats
from app.main import app
from app.replay import clock

U = config.UNITS
W = "SofiaWallet111"


def et(hh, mm):
    return datetime(2026, 9, 25, hh, mm, tzinfo=config.ET)


def row(id, hh, mm, kind, usd, symbol=None, qty=None, price=None, sig=None):
    return {"id": id, "ts": config.iso(et(hh, mm)), "kind": kind, "symbol": symbol,
            "qty_units": None if qty is None else round(qty * U), "price": price,
            "usd_units": round(usd * U), "signature": sig}


# The spec's placeholder story: deposit $1,000; AKAM +$11.25; TSLA −$6.40; MSFT $400 still held.
SPEC_ROWS = [
    row(1, 9, 25, "deposit", 1000),
    row(2, 9, 31, "buy", 300, "AKAM", 2.5, 120.00, "s2"),
    row(3, 9, 45, "sell", 311.25, "AKAM", 2.5, 124.50, "s3"),
    row(4, 10, 0, "buy", 200, "TSLA", 0.5, 400.00, "s4"),
    row(5, 10, 20, "sell", 193.60, "TSLA", 0.5, 387.20, "s5"),
    row(6, 10, 30, "buy", 400, "MSFT", 0.791922, 505.10, "s6"),
]
PRICES = {"MSFT": 516.17, "AKAM": 124.50, "TSLA": 387.20}


def price_fn(symbol, _t):
    return PRICES[symbol]


def test_transactions_match_contract_example():
    txs = stats.transactions(SPEC_ROWS)
    assert [t["id"] for t in txs] == [6, 5, 4, 3, 2]  # newest first, no deposits
    akam_sell = next(t for t in txs if t["id"] == 3)
    assert akam_sell == {
        "id": 3, "sim_time": "2026-09-25T09:45:00-04:00", "symbol": "AKAM", "side": "sell",
        "qty": 2.5, "price": 124.50, "usd_amount": 311.25,
        "cash_before": 700.00, "cash_after": 1011.25,
        "realized_pl": 11.25, "realized_pl_pct": 3.75, "outcome": "win",
        "opened_at": "2026-09-25T09:31:00-04:00", "held_min": 14,
        "signature": "s3", "explorer_url": "https://explorer.solana.com/tx/s3?cluster=devnet",
    }
    akam_buy = next(t for t in txs if t["id"] == 2)
    assert (akam_buy["realized_pl"], akam_buy["outcome"], akam_buy["held_min"]) == (None, None, None)
    tsla_sell = next(t for t in txs if t["id"] == 5)
    assert (tsla_sell["realized_pl"], tsla_sell["outcome"]) == (-6.40, "loss")


def test_portfolio_matches_contract_example():
    p = stats.portfolio(SPEC_ROWS, price_fn, et(10, 31))
    assert p["cash"] == 604.85
    assert p["holdings"] == [{"symbol": "MSFT", "qty": 0.791922, "avg_cost": 505.10, "price": 516.17,
                              "market_value": 408.77, "unrealized_pl": 8.77}]
    assert p["total_value"] == 1013.62 and p["deposited"] == 1000.00
    assert p["stats"] == {"total_pl": 13.62, "total_pl_pct": 1.36, "avg_win": 11.25, "avg_loss": -6.40,
                          "trade_count": 5, "win_count": 1, "loss_count": 1}


def test_average_cost_across_two_buys_and_partial_sell():
    rows = [
        row(1, 9, 30, "deposit", 1000),
        row(2, 9, 31, "buy", 100, "AKAM", 1, 100.0),
        row(3, 9, 40, "buy", 300, "AKAM", 2, 150.0),  # avg = (100 + 300) / 3 = 133.33
        row(4, 9, 50, "sell", 160, "AKAM", 1, 160.0),
    ]
    sell = stats.transactions(rows)[0]
    assert sell["realized_pl"] == round(160 - 400 / 3, 2)
    assert sell["opened_at"] == "2026-09-25T09:31:00-04:00" and sell["held_min"] == 19
    h = stats.portfolio(rows, lambda s, t: 160.0, et(9, 50))["holdings"][0]
    assert h["qty"] == 2 and h["avg_cost"] == 133.33  # unchanged by the sell


def test_average_cost_resets_when_position_closes():
    rows = [
        row(1, 9, 30, "deposit", 1000),
        row(2, 9, 31, "buy", 100, "AKAM", 1, 100.0),
        row(3, 9, 32, "sell", 110, "AKAM", 1, 110.0),
        row(4, 9, 40, "buy", 200, "AKAM", 1, 200.0),
        row(5, 9, 45, "sell", 210, "AKAM", 1, 210.0),
    ]
    last = stats.transactions(rows)[0]
    assert last["realized_pl"] == 10.0 and last["opened_at"] == "2026-09-25T09:40:00-04:00"


def test_empty_wallet():
    p = stats.portfolio([], price_fn, et(9, 30))
    assert p["cash"] == 0 and p["holdings"] == [] and p["equity_curve"] == []
    assert p["stats"]["avg_win"] is None and p["stats"]["total_pl_pct"] == 0.0


def test_equity_curve_one_point_per_minute():
    rows = [row(1, 9, 30, "deposit", 1000), row(2, 9, 31, "buy", 500, "AKAM", 5, 100.0)]
    curve = stats.equity_curve(rows, lambda s, t: 100.0 if t < et(9, 33) else 110.0, et(9, 34))
    assert [p["value"] for p in curve] == [1000.0, 1000.0, 1000.0, 1050.0, 1050.0]
    assert curve[0]["t"] == "2026-09-25T09:30:00-04:00" and len(curve) == 5


@pytest.fixture
def api():
    c = db.connect(":memory:")
    db.init(c)
    db.use(c)
    clock.reset()
    yield TestClient(app)
    db.use(None)


def test_endpoints_read_the_ledger(api):
    ledger.record(W, "deposit", None, None, None, 1000 * U, et(9, 25), "f1")
    ledger.record(W, "buy", "AKAM", 2 * U, 116.0, 232 * U, et(9, 25), "b1")
    txs = api.get("/transactions", params={"wallet": W}).json()
    assert len(txs) == 1 and txs[0]["cash_after"] == 768.0
    p = api.get("/portfolio", params={"wallet": W}).json()
    assert p["cash"] == 768.0 and p["holdings"][0]["symbol"] == "AKAM"
    assert api.get("/transactions", params={"wallet": "someone-else"}).json() == []

    api.post("/demo/reset", json={"wallet": W})
    assert api.get("/portfolio", params={"wallet": W}).json()["deposited"] == 0
