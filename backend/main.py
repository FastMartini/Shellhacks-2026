import os, requests

from datetime import datetime

from model import db, LatestStockPrices

from fastapi import FastAPI

from dotenv import load_dotenv

from sqlalchemy import func, select

load_dotenv()

ALPACA_HEADER = {
    "APCA-API-SECRET-KEY": os.getenv("ALPACA_API_SECRET"),
    "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY")
}

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/friday")
async def scan_friday_data():
    if db.scalar(select(func.count()).select_from(LatestStockPrices)) > 5500:
        return {
            "msg": "Table already filled"
        }
    
    assets = requests.get(
        "https://paper-api.alpaca.markets/v2/assets",
        headers=ALPACA_HEADER,
        params={"status": "active", "asset_class": "us_equity", "exchange": "NASDAQ"},
    ).json()
    
    symbols = [a["symbol"] for a in assets if a["tradable"]]
    
    # 2. Batch symbols (URL length limits mean you can't send thousands at once)
    def chunks(lst, size=100):
        for i in range(0, len(lst), size):
            yield lst[i:i + size]

    # 3. Fetch Friday's bars for each batch
    friday = "2026-09-25"
    all_bars = {}
    for batch in chunks(symbols):
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
        new_record = LatestStockPrices(
            symbol=sym,
            high=details["h"],
            low=details["l"],
            open=details["o"],
            close=details["c"],
            volume_weighted_price=details["vw"],
            number_of_trades=details["n"],
            timestamp=datetime.fromisoformat(details["t"].replace("Z", "+00:00")),
            volume=details["v"]
        )
        
        db.add(new_record)
        
        db.commit()

    return {
        "msg": "Success"
    }
