from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import config, db, prices
from app.main import app
from app.replay import ReplayClock, clock


class FakeTime:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def et(hh, mm):
    return datetime(2026, 9, 25, hh, mm, tzinfo=config.ET)


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.init(c)
    db.use(c)
    clock.reset()
    yield c
    db.use(None)


def test_clock_starts_paused_at_925():
    c = ReplayClock(FakeTime())
    assert c.state() == {"mode": "replay", "sim_time": "2026-09-25T09:25:00-04:00", "speed": 30, "running": False}


def test_clock_advances_at_speed_and_pauses():
    ft = FakeTime()
    c = ReplayClock(ft)
    c.start()
    ft.t = 10  # 10 s wall × 30 = 5 sim minutes
    assert c.sim_time == et(9, 30)
    c.pause()
    ft.t = 100
    assert c.sim_time == et(9, 30)


def test_speed_change_keeps_elapsed_time():
    ft = FakeTime()
    c = ReplayClock(ft)
    c.start()
    ft.t = 10  # 9:30 at 30×
    c.set_speed(60)
    ft.t = 20  # +10 min at 60×
    assert c.sim_time == et(9, 40)


def test_clock_stops_at_close():
    ft = FakeTime()
    c = ReplayClock(ft)
    c.start()
    ft.t = 10_000
    assert c.sim_time == config.MARKET_CLOSE
    assert c.running is False


def test_price_at_uses_prev_close_then_last_bar(conn):
    conn.execute("INSERT INTO daily_bars VALUES ('AKAM', '2026-09-24', 100.0, 1000)")
    conn.executemany(
        "INSERT INTO bars VALUES ('AKAM', ?, 0, 0, 0, ?, ?)",
        [(config.iso(et(9, 30)), 115.0, 500), (config.iso(et(9, 32)), 118.0, 300)],
    )
    assert prices.price_at("AKAM", et(9, 25)) == 100.0   # before the first bar
    assert prices.price_at("AKAM", et(9, 31)) == 115.0   # carries forward over the empty minute
    assert prices.price_at("AKAM", et(15, 0)) == 118.0   # after the last bar
    assert prices.volume_since("AKAM", et(9, 30), et(9, 32)) == 800


def test_http_contracts(conn):
    api = TestClient(app)
    assert api.get("/replay/state").json()["sim_time"] == "2026-09-25T09:25:00-04:00"

    state = api.post("/replay/control", json={"action": "seek", "to": "2026-09-25T10:00:00-04:00"}).json()
    assert state == {"mode": "replay", "sim_time": "2026-09-25T10:00:00-04:00", "speed": 30, "running": False}

    rows = api.get("/prices").json()
    assert len(rows) == 19 and set(rows[0]) == {"symbol", "price", "prev_close", "change_pct", "sim_time"}

    r = api.get("/prices/NOPE")
    assert r.status_code == 404 and r.json()["error"] == "unknown_symbol"

    r = api.post("/replay/control", json={"action": "jump"})
    assert r.status_code == 422 and r.json()["error"] == "invalid_request"

    r = api.post("/replay/next-alert")
    assert r.status_code == 404 and r.json()["error"] == "no_next_alert"

    conn.execute("INSERT INTO alerts VALUES ('MSFT-1015', 'MSFT', ?, 510, 3.1, 2.4, '[]', NULL, NULL)",
                 (config.iso(et(10, 15)),))
    assert api.post("/replay/next-alert").json()["sim_time"] == "2026-09-25T10:15:00-04:00"


def test_cors_allows_vite():
    r = TestClient(app).get("/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
