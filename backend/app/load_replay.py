"""One-off replay data loader (BUILD_SPEC.md → Replay data). Run from backend/ before the demo:

    python -m app.load_replay

Downloads Friday's 1-minute SIP bars (4:00 AM–8:00 PM ET) into `bars`, the 20 prior sessions into
`daily_bars`, and Finnhub company news for Sept 24–25 into `news`. Everything is fetched and checked before
anything is written, then written in one transaction that replaces the old rows for these symbols, so a
failed run changes nothing and a rerun is safe. The API never calls this; it only reads what it wrote.

Run it before starting uvicorn, or restart uvicorn afterwards: the scanner computes alerts at startup.
Needs ALPACA_API_KEY, ALPACA_API_SECRET and FINNHUB_API_KEY in backend/.env (see .env.example).
"""

import os
import sqlite3
import sys
from datetime import datetime, time, timedelta

import httpx

from . import config, db

BARS_URL = "https://data.alpaca.markets/v2/stocks/bars"
NEWS_URL = "https://finnhub.io/api/v1/company-news"
DAY_START = datetime.combine(config.REPLAY_DATE, time(4, 0), tzinfo=config.ET)
DAY_END = datetime.combine(config.REPLAY_DATE, time(20, 0), tzinfo=config.ET)
BASELINE_SESSIONS = 20
# 20 sessions plus weekends and holidays fit comfortably in 45 calendar days.
BASELINE_LOOKBACK = timedelta(days=45)
PAGE_LIMIT = 10_000
# Sept 24–25: covers the scanner's 24 h news window for any alert on the replay day.
NEWS_FROM = config.REPLAY_DATE - timedelta(days=1)


class LoadError(RuntimeError):
    """The download failed or came back incomplete; nothing was written."""


def _env(*names: str) -> list[str]:
    values = [os.getenv(n) for n in names]
    if not all(values):
        raise LoadError(f"{' and '.join(names)} must be set in backend/.env")
    return values


def _get(url: str, headers: dict, params: dict, what: str):
    """GET JSON, turning timeouts, network errors and non-2xx responses into LoadError."""
    try:
        r = httpx.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise LoadError(f"HTTP {e.response.status_code} for {what}: {e.response.text[:200]}") from e
    except httpx.HTTPError as e:
        raise LoadError(f"Could not fetch {what}: {e}") from e
    return r.json()


def fetch_bars(symbols: list[str], timeframe: str, start: str, end: str) -> dict[str, list[dict]]:
    """Every bar for `symbols`, following next_page_token: Alpaca's limit counts bars across all symbols."""
    key, secret = _env("ALPACA_API_KEY", "ALPACA_API_SECRET")
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    params = {
        "symbols": ",".join(symbols),
        "timeframe": timeframe,
        "start": start,
        "end": end,
        "feed": "sip",
        "limit": PAGE_LIMIT,
    }
    out: dict[str, list[dict]] = {s: [] for s in symbols}
    while True:
        page = _get(BARS_URL, headers, params, f"Alpaca {timeframe} bars")
        for sym, bars in (page.get("bars") or {}).items():
            out.setdefault(sym, []).extend(bars)
        token = page.get("next_page_token")
        if not token:
            return out
        params["page_token"] = token


def fetch_news(symbols: list[str]) -> list[tuple]:
    """`news` rows for Sept 24–25 ET, one Finnhub call per symbol (free tier: 60 calls/min).

    ETFs like SPY and QQQ usually have no company news, so an empty list is not an error.
    """
    (key,) = _env("FINNHUB_API_KEY")
    headers = {"X-Finnhub-Token": key}
    rows = []
    for sym in symbols:
        items = _get(
            NEWS_URL,
            headers,
            {"symbol": sym, "from": NEWS_FROM.isoformat(), "to": config.REPLAY_DATE.isoformat()},
            f"Finnhub news for {sym}",
        )
        if not isinstance(items, list):
            raise LoadError(f"Unexpected Finnhub response for {sym}: {str(items)[:200]}")
        seen = set()
        for item in items:
            published = datetime.fromtimestamp(item["datetime"], config.ET)
            headline = (item.get("headline") or "").strip()
            # Finnhub's from/to are loose, and it repeats stories from different sources.
            if not headline or not NEWS_FROM <= published.date() <= config.REPLAY_DATE:
                continue
            if (published, headline) in seen:
                continue
            seen.add((published, headline))
            rows.append((sym, config.iso(published), headline, item.get("url") or None))
    return rows


def _et(t: str) -> datetime:
    """Alpaca's UTC bar time ("...Z") in Eastern time."""
    return datetime.fromisoformat(t).astimezone(config.ET)


def fetch(symbols: list[str]) -> tuple[list[tuple], list[tuple], list[tuple]]:
    """Rows for `bars`, `daily_bars` and `news`, or LoadError if any symbol is missing bars."""
    minute = fetch_bars(symbols, "1Min", config.iso(DAY_START), config.iso(DAY_END))
    # Fetch through the replay day and filter here, so the prior session is never cut off by how Alpaca
    # reads a date-only `end`.
    daily = fetch_bars(
        symbols, "1Day", (config.REPLAY_DATE - BASELINE_LOOKBACK).isoformat(), config.REPLAY_DATE.isoformat()
    )

    bar_rows, daily_rows, problems = [], [], []
    for sym in symbols:
        bars = minute.get(sym, [])
        if not bars:
            problems.append(f"{sym}: no minute bars for {config.REPLAY_DATE}")
        # Stored with the Eastern offset: price_at compares ts as text.
        bar_rows += [(sym, config.iso(_et(b["t"])), b["o"], b["h"], b["l"], b["c"], int(b["v"])) for b in bars]

        prior = sorted(
            (_et(b["t"]).date().isoformat(), b["c"], int(b["v"]))
            for b in daily.get(sym, [])
            if _et(b["t"]).date() < config.REPLAY_DATE
        )[-BASELINE_SESSIONS:]
        if len(prior) < BASELINE_SESSIONS:
            problems.append(f"{sym}: {len(prior)} of {BASELINE_SESSIONS} prior daily bars")
        daily_rows += [(sym, *row) for row in prior]

    if problems:
        raise LoadError("Incomplete data from Alpaca:\n  " + "\n  ".join(problems))
    return bar_rows, daily_rows, fetch_news(symbols)


def save(
    conn: sqlite3.Connection, symbols: list[str], bar_rows: list[tuple], daily_rows: list[tuple], news_rows: list[tuple]
) -> None:
    """Replace these symbols' bars, daily_bars and news in one transaction."""
    marks = ",".join("?" * len(symbols))
    with conn:
        for table in ("bars", "daily_bars", "news"):
            conn.execute(f"DELETE FROM {table} WHERE symbol IN ({marks})", symbols)
        conn.executemany("INSERT INTO bars VALUES (?, ?, ?, ?, ?, ?, ?)", bar_rows)
        conn.executemany("INSERT INTO daily_bars VALUES (?, ?, ?, ?)", daily_rows)
        conn.executemany("INSERT INTO news VALUES (?, ?, ?, ?)", news_rows)


def load(conn: sqlite3.Connection, symbols: list[str] = config.SYMBOLS) -> dict:
    bar_rows, daily_rows, news_rows = fetch(symbols)
    save(conn, symbols, bar_rows, daily_rows, news_rows)
    return {"symbols": len(symbols), "bars": len(bar_rows), "daily_bars": len(daily_rows), "news": len(news_rows)}


def main() -> int:
    conn = db.connect()
    db.init(conn)
    try:
        counts = load(conn)
    except LoadError as e:
        print(f"Load failed, nothing was written.\n{e}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    print(
        f"Loaded {counts['bars']} minute bars, {counts['daily_bars']} daily bars and {counts['news']} headlines "
        f"for {counts['symbols']} symbols."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
