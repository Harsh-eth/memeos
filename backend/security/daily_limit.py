from __future__ import annotations

import threading
from datetime import date, timezone


def _utc_date() -> date:
    return date.today()  # calendar day in server local TZ; use UTC if server is UTC


class DailyIPLimiter:
    """Strict per-IP daily cap with acquire/release so failed pipelines do not consume quota."""

    def __init__(self, max_per_day: int) -> None:
        self._max = max(1, max_per_day)
        self._lock = threading.Lock()
        self._by_ip: dict[str, tuple[date, int]] = {}

    def _day_count(self, ip: str) -> tuple[date, int]:
        d0 = _utc_date()
        d, c = self._by_ip.get(ip, (d0, 0))
        if d != d0:
            return d0, 0
        return d, c

    def acquire(self, ip: str) -> tuple[bool, int]:
        """
        Reserve one generation slot. Returns (ok, remaining_after_this_if_ok).
        Call release(ip) if generation fails after acquire.
        """
        with self._lock:
            d, c = self._day_count(ip)
            if c >= self._max:
                return False, 0
            c += 1
            self._by_ip[ip] = (d, c)
            return True, self._max - c

    def release(self, ip: str) -> None:
        """Undo one slot (e.g. after server error before returning success)."""
        with self._lock:
            d, c = self._day_count(ip)
            if c <= 0:
                return
            c -= 1
            self._by_ip[ip] = (d, c)

    def snapshot(self, ip: str) -> tuple[int, int]:
        """Current (used, remaining) without mutating."""
        with self._lock:
            d, c = self._day_count(ip)
            used = min(c, self._max)
            return used, max(0, self._max - used)
