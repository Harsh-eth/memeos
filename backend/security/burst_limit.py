from __future__ import annotations

import threading
import time


class BurstLimiter:
    """At most one request per IP every `interval_sec` (wall-clock seconds)."""

    def __init__(self, interval_sec: float = 3.0) -> None:
        self._interval = float(interval_sec)
        if self._interval <= 0:
            self._interval = 3.0
        self._lock = threading.Lock()
        self._last_wall: dict[str, float] = {}

    def allow(self, ip: str) -> bool:
        now = time.time()
        with self._lock:
            last = self._last_wall.get(ip)
            if last is not None and (now - last) < self._interval:
                return False
            self._last_wall[ip] = now
            return True
