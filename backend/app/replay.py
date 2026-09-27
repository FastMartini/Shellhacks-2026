"""In-memory replay clock for Friday Sept 25. Lives in one process, so run uvicorn with a single worker."""

import time
from datetime import datetime, timedelta
from typing import Callable

from . import config


class ReplayClock:
    def __init__(self, now: Callable[[], float] = time.monotonic):
        self._now = now
        self.reset()

    def reset(self) -> None:
        """Back to the 4:00 AM pre-market open, paused, at default speed."""
        self.speed = config.DEFAULT_SPEED
        self.running = False
        self._anchor_sim = config.REPLAY_START
        self._anchor_wall = self._now()

    @property
    def sim_time(self) -> datetime:
        if not self.running:
            return self._anchor_sim
        elapsed = (self._now() - self._anchor_wall) * self.speed
        t = self._anchor_sim + timedelta(seconds=elapsed)
        if t >= config.SCANNER_CLOSE:
            # Keep the scanner moving through its short post-close window.
            self._freeze(config.SCANNER_CLOSE)
            return config.SCANNER_CLOSE
        return t

    def _freeze(self, at: datetime) -> None:
        self._anchor_sim = at
        self._anchor_wall = self._now()
        self.running = False

    def start(self) -> None:
        if self.running or self.sim_time >= config.SCANNER_CLOSE:
            return
        self._anchor_sim = self.sim_time
        self._anchor_wall = self._now()
        self.running = True

    def pause(self) -> None:
        self._freeze(self.sim_time)

    def set_speed(self, speed: float) -> None:
        # Re-anchor first so time already elapsed keeps the old speed.
        self._anchor_sim = self.sim_time
        self._anchor_wall = self._now()
        self.speed = max(config.MIN_SPEED, min(config.MAX_SPEED, speed))

    def seek(self, to: datetime) -> None:
        """Jump to `to` (clamped to 4:00 AM–4:15 PM on the replay day) and pause."""
        to = max(config.PREMARKET_OPEN, min(config.SCANNER_CLOSE, to.astimezone(config.ET)))
        self._freeze(to)

    def state(self) -> dict:
        return {
            "mode": "replay",
            "sim_time": config.iso(self.sim_time),
            "speed": self.speed,
            "running": self.running,
        }


clock = ReplayClock()
