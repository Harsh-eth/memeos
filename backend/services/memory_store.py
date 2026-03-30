from __future__ import annotations

import threading
import time
from typing import Any, Dict, List


def _caption_pair(caps: dict[str, Any] | None) -> tuple[str, str]:
    if not caps:
        return "", ""
    return (
        str(caps.get("top_text", "")).strip().lower(),
        str(caps.get("bottom_text", "")).strip().lower(),
    )


def _is_similar(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return a in b or b in a


class MemoryStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.memory: List[Dict[str, Any]] = []

    def add(self, item: Dict[str, Any]) -> None:
        score = int(item.get("score") or 0)
        if score < 6:
            return

        caps = item.get("captions") if isinstance(item.get("captions"), dict) else {}
        new_top, new_bottom = _caption_pair(caps)

        if not new_top and not new_bottom:
            return

        entry = {**item, "timestamp": int(time.time())}

        with self._lock:
            for m in self.memory:
                old_caps = m.get("captions") if isinstance(m.get("captions"), dict) else {}
                old_top, old_bottom = _caption_pair(old_caps)

                # exact duplicate
                if old_top == new_top and old_bottom == new_bottom:
                    return

                # similar duplicate
                if _is_similar(old_top, new_top) or _is_similar(old_bottom, new_bottom):
                    return

            self.memory.append(entry)

            # keep max 100
            if len(self.memory) > 100:
                self.memory = self.memory[-100:]

    def get_top(self, mode: str, limit: int = 3) -> list[dict[str, Any]]:
        mode_key = (mode or "").strip().lower()

        with self._lock:
            filtered = [
                x
                for x in self.memory
                if str(x.get("mode", "")).strip().lower() == mode_key
            ]

            now = int(time.time())

            # score + recency
            sorted_mem = sorted(
                filtered,
                key=lambda x: (
                    int(x.get("score", 0)) * 2
                    + max(0, 100 - (now - int(x.get("timestamp", now))))
                ),
                reverse=True,
            )

            seen_patterns = set()
            result: list[dict[str, Any]] = []

            for m in sorted_mem:
                caps = m.get("captions") if isinstance(m.get("captions"), dict) else {}
                pattern = str(caps.get("top_text", "")).strip().lower()[:20]

                if pattern in seen_patterns:
                    continue

                seen_patterns.add(pattern)
                result.append(m)

                if len(result) >= limit:
                    break

            return [dict(x) for x in result]



