"""Vault (Matthew). BUILD_SPEC.md → Interface contracts → 3, and → Vault.

Quote → sign → submit: /trade/quote prices the trade at the replay clock and builds an unsigned legacy
transaction (vault pays the fee); Phantom signs first; /trade/submit checks it's the quoted transaction,
co-signs, sends, waits for `confirmed`, then writes the ledger row. Quotes live in memory, so run uvicorn
with a single worker.
"""

import base64
import math
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from solana.exceptions import SolanaRpcException
from solana.rpc.core import RPCException, TransactionExpiredBlockheightExceededError, UnconfirmedTxError
from solders.keypair import Keypair
from solders.message import Message
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.transaction import Transaction, TransactionError

from .. import chain, config, ledger, prices, stats
from ..errors import ApiError
from ..replay import clock

router = APIRouter()

FAUCET_USD = 1000
QUOTE_TTL_S = 30
U = config.UNITS
LOST_TOUCH = "Lost touch with Solana devnet mid-trade; submit again to check whether it went through"
# The trade may have landed, but we couldn't see it confirm: devnet stopped answering or only sent errors, or it
# was only processed when the blockhash expired.
MAYBE_LANDED = (SolanaRpcException, UnconfirmedTxError)


class WalletBody(BaseModel):
    wallet: str


class QuoteBody(BaseModel):
    wallet: str
    symbol: str
    side: Literal["buy", "sell"]
    usd_amount: float | None = None
    qty: float | None = None
    sell_all: bool = False


class SubmitBody(BaseModel):
    quote_id: str
    signed_tx_base64: str


@dataclass
class Quote:
    wallet: str
    symbol: str
    side: str
    price: float
    qty_units: int
    usd_units: int
    sim_time: datetime
    message: Message
    last_valid_block_height: int
    expires_at: float  # time.monotonic()


quotes: dict[str, Quote] = {}
# A submit the front-end retries (a double click, or a response lost to a dropped connection) must not trade twice:
# a quote in flight answers 409 submit_in_progress, and a finished one returns the trade it already made.
in_flight: set[str] = set()
submitted: dict[str, tuple[str, int]] = {}  # quote_id → (wallet, ledger row id)
# Sent, but not seen to confirm (MAYBE_LANDED). It may have landed, so a resubmit checks this signature instead of
# sending again.
unconfirmed: dict[str, tuple[Quote, Signature]] = {}
# Each wallet gets demo dollars once (until /demo/reset), so a second click can't double the account: seed_demo.py
# already deposits for the demo wallet. Wallets whose faucet is running, so two quick clicks don't both mint.
funding: set[str] = set()


def _owner(wallet: str) -> Pubkey:
    try:
        return Pubkey.from_string(wallet)
    except ValueError:
        raise ApiError(400, "invalid_wallet", f"{wallet!r} isn't a Solana wallet address")


def _vault() -> Keypair:
    try:
        return chain.vault()
    except FileNotFoundError:
        raise ApiError(503, "vault_not_configured",
                       "No vault keypair: get keys/vault-keypair.json from the team or run scripts.setup_devnet")


@contextmanager
def _chain_errors(expired: tuple[str, str], unavailable: str = "Couldn't reach Solana devnet; try again"):
    """Turns devnet failures into the {error, message} shape. `expired` = (code, message) for a lapsed blockhash."""
    try:
        yield
    except MAYBE_LANDED:
        raise ApiError(502, "chain_unavailable", unavailable)
    except RPCException as e:  # e.g. preflight simulation failed
        raise ApiError(409, "tx_failed", f"Devnet rejected the transaction: {getattr(e.args[0], 'message', e)}")
    except TransactionExpiredBlockheightExceededError:
        raise ApiError(409, *expired)
    except RuntimeError as e:  # chain.confirm: landed but failed on-chain
        raise ApiError(409, "tx_failed", str(e))


def _amounts(body: QuoteBody, price: float) -> tuple[int | None, int | None]:
    """(qty_units, usd_units) from the request. Buys burn exactly usd_amount and round qty down to 6 decimals;
    sells mint qty × price rounded down. qty_units is None for sell_all: it's the on-chain balance, read later."""
    given = [body.usd_amount is not None, body.qty is not None, body.sell_all]
    if sum(given) != 1:
        raise ApiError(400, "invalid_amount", "Send exactly one of usd_amount, qty or sell_all")
    if body.sell_all:
        if body.side == "buy":
            raise ApiError(400, "invalid_amount", "sell_all only works for sells")
        return None, None
    if (body.usd_amount if body.usd_amount is not None else body.qty) <= 0:
        raise ApiError(400, "invalid_amount", "The amount must be more than zero")

    if body.usd_amount is not None:
        usd_units = round(body.usd_amount * U)
        qty_units = math.floor(usd_units / price)
        if body.side == "sell":
            usd_units = math.floor(qty_units * price)
    else:
        qty_units = round(body.qty * U)
        usd_units = round(qty_units * price) if body.side == "buy" else math.floor(qty_units * price)
    if qty_units <= 0 or usd_units <= 0:
        raise ApiError(400, "invalid_amount", "That amount rounds to zero")
    return qty_units, usd_units


@router.post("/faucet")
async def faucet(body: WalletBody):
    owner, vault = _owner(body.wallet), _vault()
    if body.wallet in funding or any(r["kind"] == "deposit" for r in ledger.rows(body.wallet)):
        raise ApiError(409, "already_funded", f"This wallet already has its ${FAUCET_USD:,} in demo dollars")
    units = FAUCET_USD * U
    funding.add(body.wallet)
    try:
        with _chain_errors(("tx_failed", "The faucet transaction expired before it landed; try again")):
            async with chain.client() as rpc:
                sig = await chain.faucet(rpc, vault, chain.mints()["dUSD"], owner, units)
        ledger.record(body.wallet, "deposit", None, None, None, units, clock.sim_time, str(sig))
    finally:
        funding.discard(body.wallet)
    return {"signature": str(sig), "usd_amount": FAUCET_USD}


@router.post("/trade/quote")
async def trade_quote(body: QuoteBody):
    symbol = body.symbol.upper()
    if symbol not in config.SYMBOLS:
        raise ApiError(404, "unknown_symbol", f"{body.symbol} isn't one of the 19 supported stocks")
    owner, vault, mints = _owner(body.wallet), _vault(), chain.mints()
    sim_time = clock.sim_time
    price = prices.price_at(symbol, sim_time)
    qty_units, usd_units = _amounts(body, price)
    dusd, stock = mints["dUSD"], mints[symbol]

    with _chain_errors(("quote_expired", "The quote expired; quote again")):
        async with chain.client() as rpc:
            if body.side == "buy":
                have = await chain.token_balance(rpc, owner, dusd)
                if have < usd_units:
                    raise ApiError(409, "insufficient_funds",
                                   f"That costs ${usd_units / U:,.2f} but the wallet has ${have / U:,.2f}")
            else:
                have = await chain.token_balance(rpc, owner, stock)
                if qty_units is None:  # sell_all burns the exact on-chain balance
                    qty_units, usd_units = have, math.floor(have * price)
                if not have or have < qty_units:
                    raise ApiError(409, "insufficient_shares",
                                   f"The wallet holds {have / U:,.6f} {symbol}, not {qty_units / U:,.6f}")
                if usd_units <= 0:
                    raise ApiError(400, "invalid_amount", "That amount rounds to zero")
            latest = (await rpc.get_latest_blockhash()).value

    pay, get = ((dusd, usd_units), (stock, qty_units)) if body.side == "buy" else ((stock, qty_units), (dusd, usd_units))
    message = chain.swap_message(vault.pubkey(), owner, pay[0], pay[1], get[0], get[1], latest.blockhash)

    now = time.monotonic()
    for qid in [q for q, v in quotes.items() if v.expires_at < now]:
        del quotes[qid]
    quote_id = uuid.uuid4().hex
    quotes[quote_id] = Quote(body.wallet, symbol, body.side, price, qty_units, usd_units, sim_time, message,
                             latest.last_valid_block_height, now + QUOTE_TTL_S)
    return {
        "quote_id": quote_id, "symbol": symbol, "side": body.side,
        "price": round(price, 2), "qty": round(qty_units / U, 6), "usd_amount": round(usd_units / U, 2),
        "sim_time": config.iso(sim_time), "expires_in_s": QUOTE_TTL_S,
        "tx_base64": base64.b64encode(chain.unsigned_tx(message)).decode(),
    }


@router.post("/trade/submit")
async def trade_submit(body: SubmitBody):
    qid = body.quote_id
    if qid in submitted:
        wallet, row_id = submitted[qid]
        return stats.transaction(ledger.rows(wallet), row_id)
    if qid in in_flight:
        raise ApiError(409, "submit_in_progress", "This trade is already being sent; wait for it to confirm")
    sent = unconfirmed.get(qid)
    q = sent[0] if sent else quotes.pop(qid, None)  # one send per quote
    if q is None or (not sent and time.monotonic() > q.expires_at):
        raise ApiError(409, "quote_expired", "The quote expired; quote again")
    in_flight.add(qid)
    try:
        if sent:  # sent before devnet stopped answering: check on it rather than send it again
            return await _recheck(qid, q, sent[1])
        return await _submit(qid, q, body.signed_tx_base64)
    finally:
        in_flight.discard(qid)


async def _submit(qid: str, q: Quote, signed_tx_base64: str) -> dict:
    try:
        raw = base64.b64decode(signed_tx_base64, validate=True)
        Transaction.from_bytes(raw)
    except ValueError:  # includes binascii.Error
        raise ApiError(400, "invalid_transaction", "signed_tx_base64 isn't a serialized transaction")

    vault = _vault()
    try:
        tx = chain.cosign(vault, raw, q.message)
    except ValueError:
        raise ApiError(400, "tx_mismatch", "The signed transaction doesn't match the quote")
    except TransactionError:
        raise ApiError(400, "not_signed", "The transaction is missing the wallet's signature")

    sig = tx.signatures[0]
    with _chain_errors(("quote_expired", "The quote expired before the transaction landed; quote again"), LOST_TOUCH):
        async with chain.client() as rpc:
            try:
                await chain.send_and_confirm(rpc, tx, q.last_valid_block_height)
            except MAYBE_LANDED:  # keep it so a resubmit can find out
                unconfirmed[qid] = (q, sig)
                raise
    return _record(qid, q, sig)


async def _recheck(qid: str, q: Quote, sig: Signature) -> dict:
    """A resubmit after we couldn't see the trade confirm (MAYBE_LANDED): did the transaction we sent land?"""
    with _chain_errors(("quote_expired", "The trade never went through; quote again"), LOST_TOUCH):
        async with chain.client() as rpc:
            try:
                await chain.confirm(rpc, sig, q.last_valid_block_height)
            except (TransactionExpiredBlockheightExceededError, RuntimeError):
                # It never landed or failed on-chain: nothing left to check. Anything else can't say whether it
                # landed, so it stays for the next resubmit.
                unconfirmed.pop(qid, None)
                raise
    unconfirmed.pop(qid, None)
    return _record(qid, q, sig)


def _record(qid: str, q: Quote, sig: Signature) -> dict:
    row_id = ledger.record(q.wallet, q.side, q.symbol, q.qty_units, q.price, q.usd_units, q.sim_time, str(sig))
    submitted[qid] = (q.wallet, row_id)
    return stats.transaction(ledger.rows(q.wallet), row_id)


@router.post("/demo/reset")
def demo_reset(body: WalletBody):
    ledger.clear(body.wallet)
    for qid in [q for q, v in quotes.items() if v.wallet == body.wallet]:
        del quotes[qid]
    for qid in [q for q, (w, _) in submitted.items() if w == body.wallet]:
        del submitted[qid]
    for qid in [q for q, (v, _) in unconfirmed.items() if v.wallet == body.wallet]:
        del unconfirmed[qid]
    clock.reset()
    return {"wallet": body.wallet, **clock.state()}
