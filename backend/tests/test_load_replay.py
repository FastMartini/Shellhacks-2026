from datetime import date, datetime, timedelta

import httpx
import pytest

from app import config, db, load_replay, prices

SYMS = ["AKAM", "MSFT"]


def et(hh, mm):
    return datetime(2026, 9, 25, hh, mm, tzinfo=config.ET)


def bar(t, c, v=100):
    return {"t": t, "o": c, "h": c, "l": c, "c": c, "v": v}


def daily_bars(n=25):
    """n sessions before the replay day (the latest closes at 100) plus the replay day itself."""
    days = [date(2026, 9, 24) - timedelta(days=i) for i in range(n)] + [date(2026, 9, 25)]
    return [bar(f"{d}T04:00:00Z", 100.0 if d == date(2026, 9, 24) else 50.0, 1000) for d in days]


# Minute bars in Alpaca's shape: UTC "Z" times, sorted by symbol, AKAM split across two pages.
PAGES = [
    {"AKAM": [bar("2026-09-25T13:31:00Z", 115.0)]},
    {"AKAM": [bar("2026-09-25T13:33:00Z", 118.0)], "MSFT": [bar("2026-09-25T13:30:00Z", 510.0)]},
]


def news(when, headline, url="https://example.com/a"):
    """A Finnhub company-news item; `when` is an Eastern datetime."""
    return {"datetime": int(when.timestamp()), "headline": headline, "url": url, "source": "Example"}


NEWS = {
    "AKAM": [
        news(et(8, 15), "Akamai raises guidance"),
        news(et(8, 15), "Akamai raises guidance", "https://example.com/b"),  # same story, another source
        news(datetime(2026, 9, 24, 17, 5, tzinfo=config.ET), "Akamai to present at conference"),
        news(datetime(2026, 9, 22, 9, 0, tzinfo=config.ET), "Old story"),  # outside Sept 24-25
    ],
    "MSFT": [],
}


class FakeApis:
    """Alpaca bars and Finnhub news, in their real response shapes."""

    def __init__(self, pages=PAGES, daily=None, news=NEWS, fail=None):
        self.pages = pages
        self.daily = {s: daily_bars() for s in SYMS} if daily is None else daily
        self.news = news
        self.fail = fail  # ("1Min" | "1Day" | "news", status) to fail with
        self.calls = []

    def __call__(self, url, headers, params, timeout):
        self.calls.append(dict(params))
        request = httpx.Request("GET", url)
        kind = "news" if url == load_replay.NEWS_URL else params["timeframe"]
        if self.fail and self.fail[0] == kind:
            return httpx.Response(self.fail[1], text="nope", request=request)
        if kind == "news":
            assert headers == {"X-Finnhub-Token": "finnhub"}
            assert (params["from"], params["to"]) == ("2026-09-24", "2026-09-25")
            return httpx.Response(200, json=self.news.get(params["symbol"], []), request=request)
        if kind == "1Day":
            body = {"bars": self.daily, "next_page_token": None}
        else:
            i = int(params.get("page_token", 0))
            body = {"bars": self.pages[i], "next_page_token": str(i + 1) if i + 1 < len(self.pages) else None}
        return httpx.Response(200, json=body, request=request)


@pytest.fixture
def conn(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "key")
    monkeypatch.setenv("ALPACA_API_SECRET", "secret")
    monkeypatch.setenv("FINNHUB_API_KEY", "finnhub")
    c = db.connect(":memory:")
    db.init(c)
    return c


def count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_loads_both_pages_in_eastern_time(conn, monkeypatch):
    fake = FakeApis()
    monkeypatch.setattr(load_replay.httpx, "get", fake)
    load_replay.load(conn, SYMS)

    alpaca_calls = [c for c in fake.calls if "timeframe" in c]
    minute_calls = [c for c in alpaca_calls if c["timeframe"] == "1Min"]
    assert len(minute_calls) == 2 and minute_calls[1]["page_token"] == "1"
    assert all(c["feed"] == "sip" for c in alpaca_calls)

    # 13:31Z is 9:31 AM ET; stored as UTC text it would only match from 1:31 PM.
    assert prices.price_at("AKAM", et(9, 30), conn) == 100.0  # prev close, before the first bar
    assert prices.price_at("AKAM", et(9, 31), conn) == 115.0
    assert prices.price_at("AKAM", et(9, 33), conn) == 118.0  # second page
    assert prices.price_at("MSFT", et(9, 30), conn) == 510.0  # second page
    assert conn.execute("SELECT ts FROM bars WHERE symbol = 'MSFT'").fetchone()[0] == "2026-09-25T09:30:00-04:00"


def test_keeps_the_20_prior_sessions(conn, monkeypatch):
    monkeypatch.setattr(load_replay.httpx, "get", FakeApis())
    load_replay.load(conn, SYMS)

    dates = [r[0] for r in conn.execute("SELECT date FROM daily_bars WHERE symbol = 'AKAM' ORDER BY date")]
    assert len(dates) == 20 and dates[-1] == "2026-09-24"  # the replay day itself is excluded
    assert prices.prev_close("AKAM", conn) == 100.0


def test_second_load_replaces_rows(conn, monkeypatch):
    monkeypatch.setattr(load_replay.httpx, "get", FakeApis())
    load_replay.load(conn, SYMS)
    load_replay.load(conn, SYMS)
    assert count(conn, "bars") == 3
    assert count(conn, "daily_bars") == 40
    assert count(conn, "news") == 2


def test_loads_news_in_eastern_time(conn, monkeypatch):
    monkeypatch.setattr(load_replay.httpx, "get", FakeApis())
    load_replay.load(conn, SYMS)

    rows = [tuple(r) for r in conn.execute("SELECT * FROM news ORDER BY published_at")]
    # The duplicate and the Sept 22 story are dropped; MSFT having no news is fine.
    assert rows == [
        ("AKAM", "2026-09-24T17:05:00-04:00", "Akamai to present at conference", "https://example.com/a"),
        ("AKAM", "2026-09-25T08:15:00-04:00", "Akamai raises guidance", "https://example.com/a"),
    ]


def test_missing_finnhub_key_writes_nothing(conn, monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY")
    monkeypatch.setattr(load_replay.httpx, "get", FakeApis())
    with pytest.raises(load_replay.LoadError, match="FINNHUB_API_KEY"):
        load_replay.load(conn, SYMS)
    assert count(conn, "bars") == count(conn, "news") == 0


@pytest.mark.parametrize("fail", [("1Min", 401), ("1Day", 429), ("1Min", 500), ("news", 403)])
def test_upstream_failure_writes_nothing(conn, monkeypatch, fail):
    monkeypatch.setattr(load_replay.httpx, "get", FakeApis())
    load_replay.load(conn, SYMS)
    before = conn.execute("SELECT * FROM bars ORDER BY symbol, ts").fetchall()

    monkeypatch.setattr(load_replay.httpx, "get", FakeApis(fail=fail))
    with pytest.raises(load_replay.LoadError, match=f"HTTP {fail[1]}"):
        load_replay.load(conn, SYMS)
    assert conn.execute("SELECT * FROM bars ORDER BY symbol, ts").fetchall() == before
    assert count(conn, "daily_bars") == 40
    assert count(conn, "news") == 2


def test_missing_symbol_writes_nothing(conn, monkeypatch):
    monkeypatch.setattr(load_replay.httpx, "get", FakeApis(pages=[PAGES[0]], daily={"AKAM": daily_bars(10)}))
    with pytest.raises(load_replay.LoadError) as e:
        load_replay.load(conn, SYMS)
    assert "MSFT: no minute bars" in str(e.value)
    assert "AKAM: 10 of 20 prior daily bars" in str(e.value)
    assert count(conn, "bars") == count(conn, "daily_bars") == count(conn, "news") == 0
