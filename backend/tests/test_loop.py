"""The must-have loop end to end through the API: demo dollars → buy → sell → log → total P/L.

The vault is faked with ledger.record + stats.transaction, which is what /faucet and /trade/submit do after
the chain confirms. Prices come from bars in SQLite via the replay clock, so this also covers price_at.
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import config, db, ledger, prices, stats
from app.main import app
from app.replay import clock

U = config.UNITS
W = "SofiaWallet111"


def et(hh, mm):
    return datetime(2026, 9, 25, hh, mm, tzinfo=config.ET)


@pytest.fixture
def api():
    c = db.connect(":memory:")
    db.init(c)
    c.execute("INSERT INTO daily_bars VALUES ('AKAM', '2026-09-24', 110.0, 1000000)")
    c.executemany("INSERT INTO bars VALUES ('AKAM', ?, NULL, NULL, NULL, ?, 1000)",
                  [(config.iso(et(9, 31)), 120.0), (config.iso(et(9, 45)), 124.5)])
    db.use(c)
    clock.reset()
    yield TestClient(app)
    db.use(None)


def seek(api, hh, mm):
    assert api.post("/replay/control", json={"action": "seek", "to": config.iso(et(hh, mm))}).status_code == 200


def faucet(wallet):
    ledger.record(wallet, "deposit", None, None, None, 1000 * U, clock.sim_time, "sig-faucet")


def trade(wallet, symbol, side, qty):
    """What /trade/submit does after confirmation: record at the quoted price, return the log row."""
    price = prices.price_at(symbol, clock.sim_time)
    row_id = ledger.record(wallet, side, symbol, round(qty * U), price, round(qty * price * U),
                           clock.sim_time, f"sig-{side}")
    return stats.transaction(ledger.rows(wallet), row_id)


def test_must_have_loop(api):
    faucet(W)
    assert api.get("/portfolio", params={"wallet": W}).json()["cash"] == 1000.0

    seek(api, 9, 31)
    buy = trade(W, "AKAM", "buy", 2.5)
    assert (buy["price"], buy["usd_amount"], buy["cash_before"], buy["cash_after"]) == (120.0, 300.0, 1000.0, 700.0)
    assert buy["realized_pl"] is None

    seek(api, 9, 45)
    sell = trade(W, "AKAM", "sell", 2.5)
    assert (sell["price"], sell["cash_after"], sell["realized_pl"], sell["outcome"], sell["held_min"]) == \
        (124.5, 1011.25, 11.25, "win", 14)
    assert sell["explorer_url"] == "https://explorer.solana.com/tx/sig-sell?cluster=devnet"

    log = api.get("/transactions", params={"wallet": W}).json()
    assert log == [sell, buy]  # what submit returned is exactly what the log shows

    p = api.get("/portfolio", params={"wallet": W}).json()
    assert p["holdings"] == [] and p["cash"] == 1011.25
    assert p["stats"]["total_pl"] == 11.25 and p["stats"]["trade_count"] == 2 and p["stats"]["win_count"] == 1


def test_open_position_marks_to_replay_price(api):
    faucet(W)
    seek(api, 9, 31)
    trade(W, "AKAM", "buy", 2.5)
    seek(api, 9, 50)  # after the last bar, price carries forward at 124.50
    p = api.get("/portfolio", params={"wallet": W}).json()
    assert p["holdings"][0]["unrealized_pl"] == 11.25 and p["total_value"] == 1011.25
