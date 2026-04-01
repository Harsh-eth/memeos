from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from backend.config import settings
from backend.services.llm import chat_json

_SCORE_SYSTEM = """You are a strict meme critic. Output ONLY valid JSON with one key:
{"score": <integer>}

The integer must be from 1 to 10 (whole number only).

Score this meme pair (top + bottom) against the scenario for:
- relatability (would real people feel this?)
- emotional accuracy (matches the scenario's tension)
- punch (wit, timing, impact)

No markdown, no explanation, no other keys."""


def _clamp_score(n: int) -> int:
    return max(1, min(10, n))


class ScoreAgent:
    """Ranks caption candidates; uses chat_json like other agents (no injected llm client)."""

    async def score(self, scenario: str, captions: dict[str, Any]) -> int:
        top = str(captions.get("top_text", "")).strip()
        bottom = str(captions.get("bottom_text", "")).strip()
        payload = json.dumps(
            {
                "scenario": (scenario or "")[:4000],
                "top": top[:300],
                "bottom": bottom[:300],
            }
        )
        if settings.openai_api_key:
            try:
                data = await chat_json(_SCORE_SYSTEM, payload)
                raw = data.get("score")
                if raw is not None:
                    if isinstance(raw, (int, float)):
                        return _clamp_score(int(raw))
                    s = str(raw).strip()
                    m = re.search(r"-?\d+", s)
                    if m:
                        return _clamp_score(int(m.group(0)))
            except Exception:
                pass
        return self._mock_score(scenario, top, bottom)

    def _mock_score(self, scenario: str, top: str, bottom: str) -> int:
        blob = f"{scenario}|{top}|{bottom}".encode("utf-8")
        h = int(hashlib.sha256(blob).hexdigest(), 16)
        return 6 + (h % 5)
