from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app import config, db, scanner
from app.main import app
from app.replay import clock


def et(hour: int, minute: int) -> datetime:
    return datetime(2026, 9, 25, hour, minute, tzinfo=config.ET)


def scanner_db():
    conn = db.connect(":memory:")
    db.init(conn)
    conn.executemany(
        "INSERT INTO daily_bars VALUES ('MSFT', ?, 100.0, ?)",
        [(f"2026-08-{day:02d}", 390_000) for day in range(1, 21)],
    )
    conn.executemany(
        "INSERT INTO bars VALUES ('MSFT', ?, 100, 105, 100, ?, ?)",
        [(config.iso(et(9, 30)), 102.0, 2_500), (config.iso(et(9, 31)), 104.0, 2_500)],
    )
    return conn


def add_news(conn, when: datetime, headline="Microsoft announces major cloud agreement"):
    conn.execute(
        "INSERT INTO news VALUES ('MSFT', ?, ?, 'https://example.com/news')",
        (config.iso(when), headline),
    )


def test_large_cap_rules_drop_price_and_float_filters():
    conn = scanner_db()
    add_news(conn, et(9, 20))

    assert scanner.rebuild_alerts(conn, ["MSFT"]) == 1
    alert = scanner.visible_alerts(et(9, 31), conn)[0]
    assert alert["symbol"] == "MSFT"
    assert alert["change_pct"] == 4.0
    assert alert["rvol"] == 2.5
    assert alert["rules_passed"] == ["change", "rvol"]


def test_both_market_signals_must_pass_and_news_is_optional():
    conn = scanner_db()
    assert scanner.rebuild_alerts(conn, ["MSFT"]) == 1
    assert scanner.visible_alerts(et(9, 31), conn)[0]["headline"] is None
    add_news(conn, et(9, 20))
    conn.execute("UPDATE bars SET volume = 1")
    assert scanner.rebuild_alerts(conn, ["MSFT"]) == 0  # low relative volume
    conn.execute("UPDATE bars SET volume = 2500, close = 102")
    assert scanner.rebuild_alerts(conn, ["MSFT"]) == 0  # low price change


def test_scans_premarket_and_resets_volume_at_regular_open():
    conn = scanner_db()
    conn.execute("DELETE FROM bars")
    conn.executemany(
        "INSERT INTO bars VALUES ('MSFT', ?, 100, 105, 100, ?, ?)",
        [
            (config.iso(et(4, 0)), 104.0, 2_000),
            (config.iso(et(9, 30)), 104.0, 2_000),
        ],
    )
    add_news(conn, et(3, 50))

    assert scanner.rebuild_alerts(conn, ["MSFT"]) == 1
    alert = scanner.visible_alerts(et(4, 0), conn)[0]
    assert alert["time"] == config.iso(et(4, 0))
    assert alert["rvol"] == 2.0


def test_scans_through_415_postmarket():
    conn = scanner_db()
    conn.execute("DELETE FROM bars")
    conn.execute(
        "INSERT INTO bars VALUES ('MSFT', ?, 100, 105, 100, 104, 32000)",
        (config.iso(et(16, 15)),),
    )
    add_news(conn, et(15, 50))

    assert scanner.rebuild_alerts(conn, ["MSFT"]) == 1
    assert scanner.visible_alerts(config.SCANNER_CLOSE, conn)[0]["time"] == config.iso(et(16, 15))


def test_generic_future_and_old_news_are_not_released():
    conn = scanner_db()
    add_news(conn, et(9, 20), "Friday pre-market movers: top gainers and losers")
    add_news(conn, et(9, 32), "Microsoft announces a future catalyst")
    add_news(conn, et(9, 31) - timedelta(hours=25), "Old Microsoft announcement")
    assert scanner.rebuild_alerts(conn, ["MSFT"]) == 1
    assert scanner.visible_alerts(et(9, 31), conn)[0]["headline"] is None


def test_snapshot_keeps_news_released_after_live_signals_fall_back():
    conn = scanner_db()
    add_news(conn, et(9, 20))
    conn.execute(
        "INSERT INTO bars VALUES ('MSFT', ?, 100, 102, 100, 101, 100)",
        (config.iso(et(9, 32)),),
    )
    scanner.rebuild_alerts(conn, ["MSFT"])

    before = scanner.snapshot(et(9, 30), conn, ["MSFT"])[0]
    assert before["signals_passed"] == 1
    assert before["momentum_pass"] is False and before["rvol_pass"] is True
    assert before["news_released"] is False and before["qualified_at"] is None
    assert before["headline"] is None and before["headline_url"] is None

    qualified = scanner.snapshot(et(9, 31), conn, ["MSFT"])[0]
    assert qualified["signals_passed"] == 2
    assert qualified["news_released"] is True
    assert qualified["qualified_at"] == config.iso(et(9, 31))
    assert qualified["headline"].startswith("Microsoft")
    assert qualified["headline_url"] == "https://example.com/news"
    assert qualified["as_of"].endswith("09:31:00-04:00")

    pulled_back = scanner.snapshot(et(9, 32), conn, ["MSFT"])[0]
    assert pulled_back["signals_passed"] == 0
    assert pulled_back["momentum_pass"] is False and pulled_back["rvol_pass"] is False
    assert pulled_back["news_released"] is True
    assert pulled_back["headline_url"] == "https://example.com/news"


def test_precomputes_one_alert_but_hides_it_until_replay_reaches_it():
    conn = scanner_db()
    add_news(conn, et(9, 20))

    assert scanner.rebuild_alerts(conn, ["MSFT"]) == 1
    assert conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 1
    assert scanner.visible_alerts(et(9, 30), conn) == []
    assert len(scanner.visible_alerts(et(9, 31), conn)) == 1
    assert scanner.rebuild_alerts(conn, ["MSFT"]) == 1
    assert conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 1


def test_prefers_a_company_specific_headline_over_newer_unrelated_news():
    conn = scanner_db()
    add_news(conn, et(9, 20), "Microsoft unveils unified Copilot for enterprise customers")
    add_news(conn, et(9, 25), "Nscale raises funding led by Third Point")

    scanner.rebuild_alerts(conn, ["MSFT"])

    assert scanner.visible_alerts(et(9, 31), conn)[0]["headline"].startswith("Microsoft")


def test_alerts_http_contract_and_replay_visibility():
    conn = scanner_db()
    add_news(conn, et(9, 20))
    db.use(conn)
    clock.reset()
    try:
        with TestClient(app) as api:
            assert api.get("/alerts").json() == []
            monitored = api.get("/scanner").json()
            assert len(monitored) == len(config.SYMBOLS)
            assert set(monitored[0]) == {
                "symbol", "token_symbol", "price", "change_pct", "rvol", "momentum_pass",
                "rvol_pass", "signals_passed", "as_of", "news_released", "qualified_at",
                "headline", "headline_url",
            }
            state = api.post("/replay/next-alert").json()
            assert state["sim_time"] == config.iso(et(9, 31))
            alert = api.get("/alerts").json()[0]
            assert set(alert) == {
                "id", "symbol", "time", "price", "change_pct", "rvol",
                "rules_passed", "headline", "headline_url",
            }
    finally:
        db.use(None)
        clock.reset()
