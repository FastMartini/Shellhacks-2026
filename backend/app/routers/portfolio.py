"""Trade log and portfolio (Khalil). BUILD_SPEC.md → Interface contracts → 4.

STUB: returns the spec's placeholder numbers. Replace with average-cost stats computed from the ledger.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/transactions")
def transactions(wallet: str):
    return [
        {"id": 3, "sim_time": "2026-09-25T09:45:00-04:00", "symbol": "AKAM", "side": "sell",
         "qty": 2.5, "price": 124.50, "usd_amount": 311.25,
         "cash_before": 700.00, "cash_after": 1011.25,
         "realized_pl": 11.25, "realized_pl_pct": 3.75, "outcome": "win",
         "opened_at": "2026-09-25T09:31:00-04:00", "held_min": 14,
         "signature": "stub-signature",
         "explorer_url": "https://explorer.solana.com/tx/stub-signature?cluster=devnet"},
        {"id": 2, "sim_time": "2026-09-25T09:31:00-04:00", "symbol": "AKAM", "side": "buy",
         "qty": 2.5, "price": 120.00, "usd_amount": 300.00,
         "cash_before": 1000.00, "cash_after": 700.00,
         "realized_pl": None, "realized_pl_pct": None, "outcome": None,
         "opened_at": None, "held_min": None,
         "signature": "stub-signature",
         "explorer_url": "https://explorer.solana.com/tx/stub-signature?cluster=devnet"},
    ]


@router.get("/portfolio")
def portfolio(wallet: str):
    return {
        "cash": 604.85,
        "holdings": [{"symbol": "MSFT", "qty": 0.791922, "avg_cost": 505.10, "price": 516.17,
                      "market_value": 408.77, "unrealized_pl": 8.77}],
        "total_value": 1013.62, "deposited": 1000.00,
        "stats": {"total_pl": 13.62, "total_pl_pct": 1.36, "avg_win": 11.25, "avg_loss": -6.40,
                  "trade_count": 5, "win_count": 1, "loss_count": 1},
        "equity_curve": [{"t": "2026-09-25T09:30:00-04:00", "value": 1000.00}],
    }
