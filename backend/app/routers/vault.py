"""Vault (Matthew). BUILD_SPEC.md → Interface contracts → 3.

STUB: /faucet, /trade/quote and /trade/submit return fake data in the contract's shape and touch
neither the chain nor the ledger. /demo/reset is real.
"""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from .. import ledger
from ..replay import clock

router = APIRouter()


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


@router.post("/faucet")
def faucet(body: WalletBody):
    return {"signature": "stub-signature", "usd_amount": 1000}


@router.post("/trade/quote")
def trade_quote(body: QuoteBody):
    return {"quote_id": "stub-quote", "symbol": body.symbol.upper(), "side": body.side,
            "price": 120.00, "qty": 2.5, "usd_amount": 300.00,
            "sim_time": "2026-09-25T09:31:00-04:00", "expires_in_s": 30, "tx_base64": ""}


@router.post("/trade/submit")
def trade_submit(body: SubmitBody):
    return {"id": 2, "sim_time": "2026-09-25T09:31:00-04:00", "symbol": "AKAM", "side": "buy",
            "qty": 2.5, "price": 120.00, "usd_amount": 300.00,
            "cash_before": 1000.00, "cash_after": 700.00,
            "realized_pl": None, "realized_pl_pct": None, "outcome": None,
            "opened_at": None, "held_min": None,
            "signature": "stub-signature",
            "explorer_url": "https://explorer.solana.com/tx/stub-signature?cluster=devnet"}


@router.post("/demo/reset")
def demo_reset(body: WalletBody):
    ledger.clear(body.wallet)
    clock.reset()
    return {"wallet": body.wallet, **clock.state()}
