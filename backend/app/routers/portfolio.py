"""Trade log and portfolio (Khalil). BUILD_SPEC.md → Interface contracts → 4.

Computed from the ledger only; no chain calls, so polling every 2 seconds is safe.
"""

from fastapi import APIRouter

from .. import ledger, prices, stats
from ..replay import clock

router = APIRouter()


@router.get("/transactions")
def transactions(wallet: str):
    return stats.transactions(ledger.rows(wallet))


@router.get("/portfolio")
def portfolio(wallet: str):
    return stats.portfolio(ledger.rows(wallet), prices.price_at, clock.sim_time)
