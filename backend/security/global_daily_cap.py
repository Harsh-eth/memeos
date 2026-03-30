from __future__ import annotations

import threading
from datetime import date


class GlobalDailyCap:
    """Total successful generation slots per calendar day (server local date)."""

    def __init__(self, max_per_day: int) -> None:
        self._max = max(1, int(max_per_day))
        self._lock = threading.Lock()
        self._day = date.today()
        self._count = 0

    def _rollover(self) -> None:
        today = date.today()
        if today != self._day:
            self._day = today
            self._count = 0

    def acquire(self) -> bool:
        with self._lock:
            self._rollover()
            if self._count >= self._max:
                return False
            self._count += 1
            return True

    def release(self) -> None:
        with self._lock:
            self._rollover()
            if self._count > 0:
                self._count -= 1
