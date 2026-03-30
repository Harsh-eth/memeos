import base64
import threading
import uuid
from datetime import datetime, timezone
from typing import Any


class FeedStore:
    def __init__(self, max_items: int = 80) -> None:
        self._items: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._max = max_items

    def add(
        self,
        image_bytes: bytes,
        metadata: dict[str, Any],
        source: str = "user",
    ) -> dict[str, Any]:
        item = {
            "id": str(uuid.uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "image_base64": base64.b64encode(image_bytes).decode("ascii"),
            "metadata": metadata,
        }
        with self._lock:
            self._items.insert(0, item)
            self._items = self._items[: self._max]
        return item

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._items[:limit])
