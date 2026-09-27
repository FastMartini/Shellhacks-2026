import os
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

ET = ZoneInfo("America/New_York")

REPLAY_DATE = date(2026, 9, 25)
PREMARKET_OPEN = datetime.combine(REPLAY_DATE, time(4, 0), tzinfo=ET)
REPLAY_START = datetime.combine(REPLAY_DATE, time(7, 0), tzinfo=ET)
MARKET_OPEN = datetime.combine(REPLAY_DATE, time(9, 30), tzinfo=ET)
MARKET_CLOSE = datetime.combine(REPLAY_DATE, time(16, 0), tzinfo=ET)
SCANNER_CLOSE = datetime.combine(REPLAY_DATE, time(16, 15), tzinfo=ET)

DEFAULT_SPEED = 30
MIN_SPEED, MAX_SPEED = 1, 60

SYMBOLS = [
    "AAPL", "AMD", "AMZN", "COIN", "GOOGL", "HOOD", "META", "MSFT", "MSTR", "NFLX",
    "NVDA", "PLTR", "QQQ", "SPY", "TSLA", "AKAM", "DDOG", "INTC", "ZS",
]

# Scanner rules for large-cap stocks.
MIN_CHANGE_PCT = 3.0
MIN_RVOL = 2.0
NEWS_LOOKBACK_HOURS = 24

# Prefer a catalyst that names the company represented by the stock. Short
# tickers such as ZS are intentionally omitted because substring matching them
# would produce false positives.
NEWS_IDENTITY_TERMS = {
    "AAPL": ("apple",), "AMD": ("advanced micro devices", "amd"),
    "AMZN": ("amazon",), "COIN": ("coinbase",), "GOOGL": ("alphabet", "google"),
    "HOOD": ("robinhood",), "META": ("meta", "facebook"), "MSFT": ("microsoft", "copilot"),
    "MSTR": ("microstrategy", "strategy inc"), "NFLX": ("netflix",), "NVDA": ("nvidia",),
    "PLTR": ("palantir",), "QQQ": ("nasdaq 100",), "SPY": ("s p 500",),
    "TSLA": ("tesla",), "AKAM": ("akamai",), "DDOG": ("datadog",),
    "INTC": ("intel",), "ZS": ("zscaler",),
}

# 1 token = 1,000,000 base units, for both dUSD and stock tokens.
UNITS = 1_000_000

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "shellhacks.db"))

FRONTEND_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def iso(dt: datetime) -> str:
    """sim_time format: ISO 8601 with the Eastern offset, e.g. 2026-09-25T09:47:00-04:00."""
    return dt.astimezone(ET).isoformat(timespec="seconds")
