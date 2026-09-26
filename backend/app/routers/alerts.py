"""Alerts (Diego). BUILD_SPEC.md → Interface contracts → 2.

STUB: returns fake data in the contract's shape. Replace with alerts read from SQLite.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/alerts")
def list_alerts():
    return [
        {"id": "AKAM-0931", "symbol": "AKAM", "time": "2026-09-25T09:31:00-04:00",
         "price": 120.00, "change_pct": 8.7, "rvol": 6.8,
         "rules_passed": ["rvol", "change", "news"],
         "headline": "Stub headline published before 9:31", "headline_url": "https://example.com"},
    ]
