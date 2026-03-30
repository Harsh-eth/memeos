from __future__ import annotations

import threading
import time
from typing import Final

_TTL_SEC: Final[float] = 60.0


class ReplayGuard:
    """Reject reuse of the same request signature within a short TTL window."""

    def __init__(self, ttl_sec: float = _TTL_SEC) -> None:
        self._ttl = float(ttl_sec)
        self._lock = threading.Lock()
        # signature -> (client timestamp, server time when stored)
        self._entries: dict[str, tuple[int, float]] = {}

    def check_and_store(self, signature: str, timestamp: int) -> bool:
        """
        Return True if signature is new and stored; False if replay (already seen, still valid).
        """
        sig = signature.strip().lower()
        if len(sig) != 64:
            return False
        try:
            client_ts = int(timestamp)
        except (TypeError, ValueError):
            return False
        now = time.time()
        with self._lock:
            drop = [k for k, (_, inserted) in self._entries.items() if now - inserted > self._ttl]
            for k in drop:
                del self._entries[k]
            if sig in self._entries:
                return False
            self._entries[sig] = (client_ts, now)
            return True
