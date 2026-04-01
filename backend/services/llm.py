from __future__ import annotations

import asyncio
import json
from typing import Any

import replicate

from config import settings

_client = replicate.Client(api_token=settings.REPLICATE_API_TOKEN)


def _strip_code_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        parts = t.split("```")
        if len(parts) >= 2:
            t = parts[1].strip()
    return t


async def chat_json(system: str, user: str) -> dict[str, Any]:
    """Replicate Claude Opus: return JSON object parsed from model output."""

    prompt = f"{system}\n\n{user}".strip()

    def _run() -> str:
        out = _client.run(
            "anthropic/claude-opus-4.6",
            input={"prompt": prompt, "max_tokens": 1024, "temperature": 0.7},
        )
        if isinstance(out, str):
            return out
        try:
            return "".join(out).strip()
        except Exception:
            return str(out).strip()

    text = _strip_code_fences(await asyncio.to_thread(_run))
    return json.loads(text or "{}")


async def chat_text(system: str, user: str) -> str:
    """Replicate Claude Opus: return plain text."""

    prompt = f"{system}\n\n{user}".strip()

    def _run() -> str:
        out = _client.run(
            "anthropic/claude-opus-4.6",
            input={"prompt": prompt, "max_tokens": 1024, "temperature": 0.8},
        )
        if isinstance(out, str):
            return out
        try:
            return "".join(out).strip()
        except Exception:
            return str(out).strip()

    return _strip_code_fences(await asyncio.to_thread(_run))
