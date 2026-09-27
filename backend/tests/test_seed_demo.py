"""seed_demo end to end: the real API in-process (TestClient) and the fake devnet from test_vault."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from solana.rpc.core import RPCException

from app import config, db, ledger
from app.main import app
from app.replay import clock
from scripts import demo_wallet, seed_demo
from tests.test_vault import MINTS, SOFIA, W, rpc  # noqa: F401  (rpc is the fake-devnet fixture)

U = config.UNITS


@pytest.fixture
def seeded(rpc, monkeypatch):  # noqa: F811
    conn = db.get()
    for sym, prices in {"MSTR": [("06:03", 162.12), ("07:22", 165.07)], "AKAM": [("06:05", 136.40), ("08:30", 127.93)],
                        "NVDA": [("09:10", 225.52)]}.items():
        conn.executemany("INSERT OR REPLACE INTO bars VALUES (?, ?, NULL, NULL, NULL, ?, 1000)",
                         [(sym, config.iso(seed_demo.at(t)), p) for t, p in prices])
    monkeypatch.setattr(demo_wallet, "load", lambda: SOFIA)
    api = seed_demo.Api()
    api.http = TestClient(app)
    monkeypatch.setattr(seed_demo, "Api", lambda: api)
    monkeypatch.setattr(seed_demo.wall, "sleep", lambda s: None)
    return rpc


def test_seed_rebuilds_the_log_and_leaves_the_clock_at_925(seeded):
    rpc = seeded
    rpc.balances[(SOFIA.pubkey(), MINTS["AKAM"])] = 3 * U       # left from the last rehearsal
    rpc.balances[(SOFIA.pubkey(), MINTS["dUSD"])] = 250 * U
    ledger.record(W, "deposit", None, None, None, 1000 * U, clock.sim_time, "old")

    seed_demo.seed()

    kinds = [(r["kind"], r["symbol"]) for r in ledger.rows(W)]
    assert kinds == [("deposit", None), ("buy", "MSTR"), ("buy", "AKAM"), ("sell", "MSTR"), ("sell", "AKAM"),
                     ("buy", "NVDA")]
    # Leftovers were burned first, so the chain matches the ledger: only NVDA is held, and cash is exact.
    assert rpc.balances[(SOFIA.pubkey(), MINTS["AKAM"])] == 0
    assert rpc.balances[(SOFIA.pubkey(), MINTS["MSTR"])] == 0
    assert rpc.balances[(SOFIA.pubkey(), MINTS["NVDA"])] > 0
    p = TestClient(app).get("/portfolio", params={"wallet": W}).json()
    assert round(rpc.balances[(SOFIA.pubkey(), MINTS["dUSD"])] / U, 2) == p["cash"] == 843.04
    assert (p["stats"]["win_count"], p["stats"]["loss_count"]) == (1, 1)
    assert clock.state() == {"mode": "replay", "sim_time": "2026-09-25T09:25:00-04:00", "speed": 30, "running": False}


def test_seed_retries_a_failed_transaction(seeded):
    rpc = seeded
    send = rpc.send_raw_transaction
    failures = iter([RPCException(SimpleNamespace(message="blockhash not found"))])

    async def flaky(raw):
        if len(rpc.sent) == 1:  # the first trade after the faucet fails once, before landing
            err = next(failures, None)
            if err:
                raise err
        return await send(raw)

    rpc.send_raw_transaction = flaky
    seed_demo.seed()
    assert len([r for r in ledger.rows(W) if r["kind"] != "deposit"]) == 5


def test_seed_stops_on_an_error_it_cannot_retry(seeded, monkeypatch):
    monkeypatch.setattr(seed_demo, "SCRIPT", [("06:03", "MSTR", "buy", 5000)])  # more than the $1,000 deposit
    with pytest.raises(SystemExit, match="insufficient_funds"):
        seed_demo.seed()
