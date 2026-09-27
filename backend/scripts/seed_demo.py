"""Pre-runs the demo's scripted non-live trades with the demo wallet's key (BUILD_SPEC.md → Demo script).

Before walking up: start the API, run this, then connect the demo wallet in Phantom. It:
1. Calls /demo/reset: her ledger is cleared and the clock goes back to the 4:00 AM pre-market open.
2. Burns the test tokens left from the last rehearsal, so the chain matches the empty ledger. sell_all sells
   her on-chain balance, so leftovers would skew the live trade's P/L.
3. Seeks the replay to each scripted time and trades through the real API, the same path as the front-end:
   /faucet, /trade/quote, sign with her key as Phantom would, /trade/submit. An expired quote is re-quoted and
   a failed transaction is retried; both changed nothing on-chain. If devnet stops answering mid-trade, the same
   submit is sent again, which checks whether the trade landed instead of trading twice.
4. Seeks back to 4:00 AM, paused, ready to replay early news and the live trade.

Run from backend/ with the API up (uvicorn app.main:app) on the same machine, since step 2 uses the vault key:
    ./venv/bin/python -m scripts.seed_demo            # API at http://127.0.0.1:8000, or set API_URL
    ./venv/bin/python -m scripts.seed_demo --dry-run  # price the script from SQLite; no API, no chain
"""

import argparse
import asyncio
import base64
import os
import time as wall
from datetime import datetime, time

import httpx
from solders.keypair import Keypair
from solders.transaction import Transaction
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import burn, get_associated_token_address
from spl.token.models import BurnParams

from app import chain, config, db, prices, stats
from app.errors import ApiError
from app.routers.vault import QuoteBody, _amounts
from scripts import demo_wallet

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
U = config.UNITS

# Scripted pre-market activity used to populate the demo portfolio before the live trade.
# Real Friday prices (check with --dry-run): MSTR rises (the win), AKAM fades off its Anthropic-news gap
# (the loss), and NVDA stays open so the portfolio has a holding. The live trade (MSFT or DDOG) is left for the stage.
DEPOSIT_AT = "06:00"
SCRIPT = [  # (time ET, symbol, side, usd_amount; None sells everything)
    ("06:03", "MSTR", "buy", 300),
    ("06:05", "AKAM", "buy", 200),
    ("07:22", "MSTR", "sell", None),
    ("08:30", "AKAM", "sell", None),
    ("09:10", "NVDA", "buy", 150),
]
ATTEMPTS = 3
# Safe to re-quote: an expired quote or a failed transaction left the chain as it was. chain_unavailable is not:
# the trade may have landed, so trade() submits the same quote again, which checks.
RETRYABLE = {"quote_expired", "tx_failed"}
BURNS_PER_TX = 6  # keeps each burn transaction under Solana's 1,232-byte limit


def at(hhmm: str) -> datetime:
    return datetime.combine(config.REPLAY_DATE, time.fromisoformat(hhmm), tzinfo=config.ET)


class Api:
    def __init__(self):
        self.http = httpx.Client(base_url=API_URL, timeout=120)  # a submit waits up to ~a minute for devnet

    def post(self, path: str, body: dict) -> httpx.Response:
        try:
            return self.http.post(path, json=body)
        except httpx.HTTPError as e:
            raise SystemExit(f"Can't reach the API at {API_URL} ({e}). Start it: uvicorn app.main:app")

    def ok(self, path: str, body: dict) -> dict:
        r = self.post(path, body)
        if r.is_error:
            raise SystemExit(f"{path} failed: {r.json()}")
        return r.json()

    def get(self, path: str, **params) -> dict:
        return self.http.get(path, params=params).json()

    def seek(self, hhmm: str) -> None:
        self.ok("/replay/control", {"action": "seek", "to": config.iso(at(hhmm))})

    def retrying(self, what: str, attempt_once) -> dict:
        """Runs attempt_once() → Response until it succeeds, retrying only what's safe to retry."""
        err: dict = {}
        for attempt in range(1, ATTEMPTS + 1):
            r = attempt_once()
            if r.is_success:
                return r.json()
            err = r.json()
            if err.get("error") not in RETRYABLE or attempt == ATTEMPTS:
                break
            print(f"  {what}: {err['error']} ({err['message']}); trying again")
            wall.sleep(2)
        raise SystemExit(f"{what} failed: {err.get('error')}: {err.get('message')}")


def sign(tx_base64: str, kp: Keypair) -> str:
    """What the front-end does: she signs first, serialized without the vault's signature."""
    tx = Transaction.from_bytes(base64.b64decode(tx_base64))
    tx.partial_sign([kp], tx.message.recent_blockhash)
    return base64.b64encode(bytes(tx)).decode()


def trade(api: Api, kp: Keypair, symbol: str, side: str, usd: float | None) -> dict:
    body = {"wallet": str(kp.pubkey()), "symbol": symbol, "side": side,
            **({"usd_amount": usd} if usd else {"sell_all": True})}

    def once() -> httpx.Response:
        q = api.post("/trade/quote", body)
        if q.is_error:
            return q
        q = q.json()
        submit = {"quote_id": q["quote_id"], "signed_tx_base64": sign(q["tx_base64"], kp)}
        r = api.post("/trade/submit", submit)
        for _ in range(ATTEMPTS - 1):  # lost touch mid-trade: the same submit checks whether it landed
            if r.is_success or r.json().get("error") != "chain_unavailable":
                break
            print(f"  {side} {symbol}: {r.json()['message']}")
            wall.sleep(2)
            r = api.post("/trade/submit", submit)
        return r

    return api.retrying(f"{side} {symbol}", once)


async def burn_leftovers(kp: Keypair) -> None:
    """Burns every test token she still holds; she signs as owner, the vault pays the fee."""
    owner, vault = kp.pubkey(), chain.vault()
    async with chain.client() as rpc:
        held = [(name, mint, await chain.token_balance(rpc, owner, mint)) for name, mint in chain.mints().items()]
        held = [h for h in held if h[2]]
        for i in range(0, len(held), BURNS_PER_TX):
            batch = held[i:i + BURNS_PER_TX]
            latest = (await rpc.get_latest_blockhash()).value
            tx = Transaction.new_signed_with_payer([
                burn(BurnParams(program_id=TOKEN_PROGRAM_ID, account=get_associated_token_address(owner, mint),
                                mint=mint, owner=owner, amount=units))
                for _, mint, units in batch
            ], vault.pubkey(), [vault, kp], latest.blockhash)
            await chain.send_and_confirm(rpc, tx, latest.last_valid_block_height)
            print("burned leftovers: " + ", ".join(f"{units / U:g} {name}" for name, _, units in batch))


def seed() -> None:
    kp = demo_wallet.load()
    wallet, api = str(kp.pubkey()), Api()
    print(f"demo wallet {wallet}")

    api.ok("/demo/reset", {"wallet": wallet})
    asyncio.run(burn_leftovers(kp))

    api.seek(DEPOSIT_AT)
    api.retrying("faucet", lambda: api.post("/faucet", {"wallet": wallet}))
    print(f"{DEPOSIT_AT}  deposit $1,000")
    for hhmm, symbol, side, usd in sorted(SCRIPT):
        api.seek(hhmm)
        t = trade(api, kp, symbol, side, usd)
        pl = f"  P/L {t['realized_pl']:+.2f}" if t["realized_pl"] is not None else ""
        print(f"{hhmm}  {side:4} {t['qty']:g} {symbol} @ {t['price']:.2f} = ${t['usd_amount']:.2f}{pl}")

    api.ok("/replay/control", {"action": "seek", "to": config.iso(config.REPLAY_START)})
    summarize(api.get("/portfolio", wallet=wallet))
    print("Clock paused at 4:00 AM. Connect the demo wallet in Phantom and start the pre-market replay.")


def dry_run() -> None:
    """The same script priced from SQLite with the vault's rounding: shows the numbers before touching devnet."""
    conn = db.connect()
    rows, held = [], {}

    def record(hhmm, kind, symbol, qty_units, price, usd_units):
        rows.append({"id": len(rows) + 1, "ts": config.iso(at(hhmm)), "kind": kind, "symbol": symbol,
                     "qty_units": qty_units, "price": price, "usd_units": usd_units, "signature": None})

    record(DEPOSIT_AT, "deposit", None, None, None, 1000 * U)
    for hhmm, symbol, side, usd in sorted(SCRIPT):
        price = prices.price_at(symbol, at(hhmm), conn)
        try:
            qty_units, usd_units = _amounts(QuoteBody(wallet="-", symbol=symbol, side=side, usd_amount=usd,
                                                      sell_all=usd is None), price)
        except ApiError as e:
            raise SystemExit(f"{hhmm} {side} {symbol}: {e.message}")
        if qty_units is None:  # sell_all
            qty_units = held.get(symbol, 0)
            usd_units = int(qty_units * price)
        held[symbol] = held.get(symbol, 0) + (qty_units if side == "buy" else -qty_units)
        record(hhmm, side, symbol, qty_units, price, usd_units)

    for t in reversed(stats.transactions(rows)):
        pl = f"  P/L {t['realized_pl']:+.2f}" if t["realized_pl"] is not None else ""
        print(f"{t['sim_time'][11:16]}  {t['side']:4} {t['qty']:g} {t['symbol']} @ {t['price']:.2f} = ${t['usd_amount']:.2f}{pl}")
    summarize(stats.portfolio(rows, lambda s, t: prices.price_at(s, t, conn), config.REPLAY_START))


def summarize(p: dict) -> None:
    s = p["stats"]
    held = ", ".join(f"{h['qty']:g} {h['symbol']}" for h in p["holdings"]) or "nothing"
    print(f"At 4:00 AM: cash ${p['cash']:.2f}, holding {held}, total ${p['total_value']:.2f}, "
          f"P/L {s['total_pl']:+.2f} ({s['win_count']} win, {s['loss_count']} loss)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="price the script from SQLite; no API, no chain")
    (dry_run if parser.parse_args().dry_run else seed)()
