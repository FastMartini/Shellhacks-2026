"""Large-cap momentum scanner backed by the replay database.

The full replay day is evaluated ahead of time, but the API only reveals an
alert after the replay clock reaches it. This keeps jump-to-next deterministic
without leaking future alerts to the UI.
"""

import json
import re
import sqlite3
from datetime import datetime, timedelta

from . import config, db, prices

# Movement roundups describe a price change without explaining its cause. A
# compact set of categories covers spelling variants without copying the
# reference scanner's term-by-term implementation.
GENERIC_NEWS_PATTERNS = (
    re.compile(r"\b(?:top|biggest)\b.*\b(?:gainers|losers|movers)\b"),
    re.compile(r"\b(?:pre|after)\s*market\s+(?:session|movers)\b"),
    re.compile(r"\b(?:morning|midday|market|stock)\s+movers\b"),
    re.compile(r"\bstocks?\s+moving\b"),
    re.compile(r"\bshares?\s+(?:are\s+)?trading\s+(?:higher|lower)\b"),
    re.compile(r"\bwhy\s+(?:is|are|shares?)\b"),
    re.compile(r"\bmarket\s+update\b"),
    re.compile(r"\bwatchlist\b"),
)


def is_quality_catalyst(headline: str) -> bool:
    normalized = _normalize_headline(headline)
    return bool(normalized) and not any(pattern.search(normalized) for pattern in GENERIC_NEWS_PATTERNS)


def _normalize_headline(headline: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", headline.lower()).split())


def _daily_average_volume(conn: sqlite3.Connection, symbol: str) -> float | None:
    rows = conn.execute(
        "SELECT volume FROM daily_bars WHERE symbol = ? AND date < ? ORDER BY date DESC LIMIT 20",
        (symbol, config.REPLAY_DATE.isoformat()),
    ).fetchall()
    if not rows:
        return None
    return sum(row["volume"] for row in rows) / len(rows)


def _quality_news(conn: sqlite3.Connection, symbol: str) -> list[sqlite3.Row]:
    return [
        row
        for row in conn.execute(
            "SELECT headline, url, published_at FROM news WHERE symbol = ? ORDER BY published_at",
            (symbol,),
        )
        if is_quality_catalyst(row["headline"])
    ]


def _latest_catalyst(rows: list[sqlite3.Row], symbol: str, at: datetime) -> sqlite3.Row | None:
    start = config.iso(at - timedelta(hours=config.NEWS_LOOKBACK_HOURS))
    end = config.iso(at)
    eligible = [row for row in rows if start <= row["published_at"] <= end]
    if not eligible:
        return None
    identity_terms = config.NEWS_IDENTITY_TERMS.get(symbol, ())
    named = [
        row for row in eligible
        if any(
            f" {term} " in f" {_normalize_headline(row['headline'])} "
            for term in identity_terms
        )
    ]
    return (named or eligible)[-1]


def _news_check_time(at: datetime) -> datetime:
    """Latest ten-minute replay boundary at which the scanner checks news."""
    at = at.astimezone(config.ET).replace(second=0, microsecond=0)
    return at - timedelta(minutes=at.minute % config.NEWS_CHECK_INTERVAL_MINUTES)


def _news_identity(row: sqlite3.Row | None) -> str | None:
    if row is None:
        return None
    return _normalize_headline(row["headline"])


def _released_catalyst(
    rows: list[sqlite3.Row],
    symbol: str,
    released_at: datetime,
    checked_at: datetime,
) -> sqlite3.Row | None:
    """Return the latest story exposed by a completed news check.

    Once a story has been exposed, keep carrying it forward when it ages out of
    the rolling lookback window. A later relevant story replaces it at the
    first ten-minute check that can see it.
    """
    release_check = _news_check_time(released_at)
    catalyst = _latest_catalyst(rows, symbol, release_check)
    boundary = release_check + timedelta(minutes=config.NEWS_CHECK_INTERVAL_MINUTES)
    while boundary <= checked_at:
        catalyst = _latest_catalyst(rows, symbol, boundary) or catalyst
        boundary += timedelta(minutes=config.NEWS_CHECK_INTERVAL_MINUTES)
    return catalyst


def _session_start(at: datetime) -> datetime:
    if at < config.MARKET_OPEN:
        return config.PREMARKET_OPEN
    if at < config.MARKET_CLOSE:
        return config.MARKET_OPEN
    return config.MARKET_CLOSE


def _signal_metrics(conn: sqlite3.Connection, symbol: str, at: datetime) -> dict:
    """Current minute's two scanner signals for one stock."""
    at = at.astimezone(config.ET).replace(second=0, microsecond=0)
    at = max(config.PREMARKET_OPEN, min(config.SCANNER_CLOSE, at))
    previous_close = prices.prev_close(symbol, conn)
    price = prices.price_at(symbol, at, conn)
    average_daily_volume = _daily_average_volume(conn, symbol)
    session_start = _session_start(at)
    elapsed_minutes = min(390, max(1, int((at - session_start).total_seconds() // 60) + 1))
    expected_volume = (average_daily_volume or 0) * elapsed_minutes / 390
    relative_volume = prices.volume_since(symbol, session_start, at, conn) / expected_volume if expected_volume else 0.0
    change_pct = (price / previous_close - 1) * 100 if previous_close else 0.0
    return {
        "price": round(price, 2),
        "change_pct": round(change_pct, 2),
        "rvol": round(relative_volume, 2),
        "momentum_pass": change_pct >= config.MIN_CHANGE_PCT,
        "rvol_pass": relative_volume >= config.MIN_RVOL,
        "as_of": config.iso(at),
    }


def snapshot(at: datetime, conn: sqlite3.Connection | None = None, symbols: list[str] | None = None) -> list[dict]:
    """All monitored stocks; released news stays available after the first 2/2 signal."""
    conn = conn or db.get()
    symbols = symbols or config.SYMBOLS
    rows = []
    for symbol in symbols:
        metrics = _signal_metrics(conn, symbol, at)
        release = conn.execute(
            "SELECT ts FROM alerts WHERE symbol = ? AND ts <= ? ORDER BY ts LIMIT 1",
            (symbol, metrics["as_of"]),
        ).fetchone()
        news_released = release is not None
        checked_at = _news_check_time(datetime.fromisoformat(metrics["as_of"]))
        news_rows = _quality_news(conn, symbol) if news_released else []
        released_at = datetime.fromisoformat(release["ts"]) if release else None
        catalyst = (
            _released_catalyst(news_rows, symbol, released_at, checked_at)
            if released_at
            else None
        )
        previous_check = checked_at - timedelta(minutes=config.NEWS_CHECK_INTERVAL_MINUTES)
        previous_catalyst = (
            _released_catalyst(news_rows, symbol, released_at, previous_check)
            if released_at and previous_check >= _news_check_time(released_at)
            else catalyst
        )
        news_is_new = (
            catalyst is not None
            and checked_at > _news_check_time(released_at)
            and _news_identity(catalyst) != _news_identity(previous_catalyst)
        )
        rows.append({
            "symbol": symbol,
            "token_symbol": f"{symbol}x-demo",
            **metrics,
            "signals_passed": int(metrics["momentum_pass"]) + int(metrics["rvol_pass"]),
            "news_released": news_released,
            "qualified_at": release["ts"] if release else None,
            "news_checked_at": config.iso(checked_at),
            "news_is_new": news_is_new,
            "news_published_at": catalyst["published_at"] if catalyst else None,
            "headline": catalyst["headline"] if catalyst else None,
            "headline_url": catalyst["url"] if catalyst else None,
        })
    return rows


def _first_alert(conn: sqlite3.Connection, symbol: str) -> dict | None:
    previous_close = prices.prev_close(symbol, conn)
    average_daily_volume = _daily_average_volume(conn, symbol)
    if previous_close <= 0 or not average_daily_volume:
        return None

    news_rows = _quality_news(conn, symbol)

    cumulative_volume = 0
    volume_window_start: datetime | None = None
    bars = conn.execute(
        "SELECT ts, close, volume FROM bars WHERE symbol = ? AND ts >= ? AND ts <= ? ORDER BY ts",
        (symbol, config.iso(config.PREMARKET_OPEN), config.iso(config.SCANNER_CLOSE)),
    )
    for bar in bars:
        at = datetime.fromisoformat(bar["ts"])
        session_start = _session_start(at)
        if session_start != volume_window_start:
            cumulative_volume = 0
            volume_window_start = session_start
        cumulative_volume += bar["volume"]
        # Daily bars do not provide historical extended-hours profiles. Use the
        # regular-session per-minute baseline within each market session, and
        # reset at 9:30 and 4:00 so pre-market volume cannot inflate regular-hours RVOL.
        elapsed_minutes = min(390, max(1, int((at - session_start).total_seconds() // 60) + 1))
        expected_volume = average_daily_volume * elapsed_minutes / 390
        relative_volume = cumulative_volume / expected_volume if expected_volume else 0.0
        change_pct = (bar["close"] / previous_close - 1) * 100

        if change_pct < config.MIN_CHANGE_PCT or relative_volume < config.MIN_RVOL:
            continue
        catalyst = _latest_catalyst(news_rows, symbol, _news_check_time(at))
        return {
            "id": f"{symbol}-{at:%H%M}",
            "symbol": symbol,
            "time": config.iso(at),
            "price": round(bar["close"], 2),
            "change_pct": round(change_pct, 2),
            "rvol": round(relative_volume, 2),
            "rules_passed": ["change", "rvol"],
            "headline": catalyst["headline"] if catalyst else None,
            "headline_url": catalyst["url"] if catalyst else None,
        }
    return None


def rebuild_alerts(
    conn: sqlite3.Connection | None = None, symbols: list[str] | None = None
) -> int:
    """Replace computed alerts with the first qualifying alert per symbol."""
    conn = conn or db.get()
    symbols = symbols or config.SYMBOLS
    marks = ",".join("?" for _ in symbols)
    alerts = [alert for symbol in symbols if (alert := _first_alert(conn, symbol)) is not None]
    with conn:
        conn.execute(f"DELETE FROM alerts WHERE symbol IN ({marks})", symbols)
        conn.executemany(
            "INSERT INTO alerts (id, symbol, ts, price, change_pct, rvol, rules_passed, headline, url) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    alert["id"], alert["symbol"], alert["time"], alert["price"], alert["change_pct"],
                    alert["rvol"], json.dumps(alert["rules_passed"]), alert["headline"], alert["headline_url"],
                )
                for alert in alerts
            ],
        )
    return len(alerts)


def visible_alerts(at: datetime, conn: sqlite3.Connection | None = None) -> list[dict]:
    conn = conn or db.get()
    rows = conn.execute(
        "SELECT * FROM alerts WHERE ts <= ? ORDER BY ts DESC", (config.iso(at),)
    ).fetchall()
    return [
        {
            "id": row["id"],
            "symbol": row["symbol"],
            "time": row["ts"],
            "price": row["price"],
            "change_pct": row["change_pct"],
            "rvol": row["rvol"],
            "rules_passed": json.loads(row["rules_passed"]),
            "headline": row["headline"],
            "headline_url": row["url"],
        }
        for row in rows
    ]
