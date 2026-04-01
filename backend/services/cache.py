from __future__ import annotations

import hashlib
import threading
from pathlib import Path


class ImageCache:
    """PNG bytes keyed by SHA-256 of prompt + tone + template + output dimensions."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    @staticmethod
    def cache_key(
        prompt_normalized: str,
        tone: str,
        template_name: str,
        width: int,
        height: int,
        mode: str = "personal",
        caption_enabled: bool = True,
    ) -> str:
        composite = (
            f"{prompt_normalized}:{tone}:{template_name}:"
            f"{int(width)}:{int(height)}:{mode}:{'cap1' if caption_enabled else 'cap0'}"
        )
        return hashlib.sha256(composite.encode("utf-8")).hexdigest()

    def get(
        self,
        prompt_normalized: str,
        tone: str,
        template_name: str,
        width: int,
        height: int,
        mode: str = "personal",
        caption_enabled: bool = True,
    ) -> bytes | None:
        key = self.cache_key(prompt_normalized, tone, template_name, width, height, mode, caption_enabled)
        path = self._root / f"{key}.png"
        with self._lock:
            if path.is_file():
                return path.read_bytes()
        return None

    def put(
        self,
        prompt_normalized: str,
        tone: str,
        template_name: str,
        width: int,
        height: int,
        png_bytes: bytes,
        mode: str = "personal",
        caption_enabled: bool = True,
    ) -> None:
        key = self.cache_key(prompt_normalized, tone, template_name, width, height, mode, caption_enabled)
        path = self._root / f"{key}.png"
        with self._lock:
            path.write_bytes(png_bytes)
