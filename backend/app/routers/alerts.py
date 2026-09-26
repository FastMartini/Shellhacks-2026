"""Large-cap momentum alerts revealed by the replay clock."""

from fastapi import APIRouter

from .. import scanner
from ..replay import clock

router = APIRouter()


@router.get("/alerts")
def list_alerts():
    return scanner.visible_alerts(clock.sim_time)
