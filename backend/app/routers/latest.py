from fastapi import APIRouter
from datetime import datetime
import requests, os

from .. import db

from ..config import SYMBOLS

router = APIRouter()

ALPACA_HEADER = {
    "APCA-API-SECRET-KEY": os.getenv("ALPACA_API_SECRET"),
    "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY")
}

@router.get("/latest/now")
def get_latest_prices():
    conn = db.get()
    
    if conn.execute("SELECT COUNT(*) FROM latest_stock_prices").fetchone()[0] >= len(SYMBOLS):
        return {"msg": "Table already filled"}

    def chunks(lst, size=100):
        for i in range(0, len(lst), size):
            yield lst[i:i + size]

    friday = "2026-09-25"
    all_bars = {}
    for batch in chunks(SYMBOLS):
        resp = requests.get(
            "https://data.alpaca.markets/v2/stocks/bars",
            headers=ALPACA_HEADER,
            params={
                "symbols": ",".join(batch),
                "timeframe": "1Day",
                "start": friday,
                "end": friday,
            },
        ).json()
        all_bars.update(resp.get("bars", {}))

    for sym in all_bars:
        details = all_bars[sym][0]
        conn.execute(
            """
            INSERT INTO latest_stock_prices
                (symbol, high, low, open, close, volume_weighted_price, number_of_trades, volume, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sym,
                details["h"],
                details["l"],
                details["o"],
                details["c"],
                details["vw"],
                details["n"],
                details["v"],
                datetime.fromisoformat(details["t"].replace("Z", "+00:00")).isoformat(),
            ),
        )

    conn.commit()
    conn.close()

    return {"msg": "Success"}