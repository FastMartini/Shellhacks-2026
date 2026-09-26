import os
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

ET = ZoneInfo("America/New_York")

REPLAY_DATE = date(2026, 9, 25)
REPLAY_START = datetime.combine(REPLAY_DATE, time(9, 25), tzinfo=ET)
MARKET_OPEN = datetime.combine(REPLAY_DATE, time(9, 30), tzinfo=ET)
MARKET_CLOSE = datetime.combine(REPLAY_DATE, time(16, 0), tzinfo=ET)

DEFAULT_SPEED = 30
MIN_SPEED, MAX_SPEED = 1, 60

SYMBOLS = [
    "AAPL", "AMD", "AMZN", "COIN", "GOOGL", "HOOD", "META", "MSFT", "MSTR", "NFLX",
    "NVDA", "PLTR", "QQQ", "SPY", "TSLA", "AKAM", "DDOG", "INTC", "ZS",
]

# 1 token = 1,000,000 base units, for both dUSD and stock tokens.
UNITS = 1_000_000

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "shellhacks.db"))

FRONTEND_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def iso(dt: datetime) -> str:
    """sim_time format: ISO 8601 with the Eastern offset, e.g. 2026-09-25T09:47:00-04:00."""
    return dt.astimezone(ET).isoformat(timespec="seconds")
