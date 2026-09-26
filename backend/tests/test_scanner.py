from datetime import datetime, timedelta

from app import config, db, scanner


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
    assert alert["token_symbol"] == "MSFTx-demo"
    assert alert["change_pct"] == 4.0
    assert alert["rvol"] == 2.5
    assert alert["rules_passed"] == ["rvol", "change", "news"]


def test_all_rules_must_pass():
    conn = scanner_db()
    assert scanner.rebuild_alerts(conn, ["MSFT"]) == 0  # no news
    add_news(conn, et(9, 20))
    conn.execute("UPDATE bars SET volume = 1")
    assert scanner.rebuild_alerts(conn, ["MSFT"]) == 0  # low relative volume
    conn.execute("UPDATE bars SET volume = 2500, close = 102")
    assert scanner.rebuild_alerts(conn, ["MSFT"]) == 0  # low price change


def test_generic_future_and_old_news_do_not_qualify():
    conn = scanner_db()
    add_news(conn, et(9, 20), "Friday pre-market movers: top gainers and losers")
    add_news(conn, et(9, 32), "Microsoft announces a future catalyst")
    add_news(conn, et(9, 31) - timedelta(hours=25), "Old Microsoft announcement")
    assert scanner.rebuild_alerts(conn, ["MSFT"]) == 0


def test_precomputes_one_alert_but_hides_it_until_replay_reaches_it():
    conn = scanner_db()
    add_news(conn, et(9, 20))

    assert scanner.rebuild_alerts(conn, ["MSFT"]) == 1
    assert conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 1
    assert scanner.visible_alerts(et(9, 30), conn) == []
    assert len(scanner.visible_alerts(et(9, 31), conn)) == 1
    assert scanner.rebuild_alerts(conn, ["MSFT"]) == 1
    assert conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 1
