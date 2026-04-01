from __future__ import annotations

import json
from typing import Any

from backend.agents.mode import MemeMode
from backend.config import settings
from backend.services.llm import chat_json

_MODE_HINTS: dict[str, str] = {
    MemeMode.PERSONAL: (
        "personal: ~70% plain relatable, ~30% self-aware pain — the laugh stings because it's true; "
        "no therapy-speak, stay punchy."
    ),
    MemeMode.ROAST: (
        "roast: sharper, more direct, slightly uncomfortable — roast the behavior/decisions in the scenario, "
        "not protected traits; no slurs."
    ),
    MemeMode.DECISION: (
        "decision: subtle warning tone — nudge which outcome is likely without naming the 'right' answer like a guidebook."
    ),
}

_CAPTION_GEN_SYSTEM = """You are the MemeOS Caption Agent. Output ONLY valid JSON with exactly these keys:
{"top_text": "...", "bottom_text": "..."}

Rules:
- Each line at most 12 words (space-separated count).
- Tie lines to the scenario specifics; honor the mode_hint tone.
- If memory_examples is non-empty: those are high-performing lines in this mode — do not copy them, but match their energy and punch.
- No generic meme filler ("when you realize", "that moment when", "nobody:", "POV:", "literally me", "it be like that", "just saying", "you know the vibe").
- No hashtags. ALL CAPS optional; keep readable."""


def _clamp_line(s: str, max_words: int = 12) -> str:
    words = s.strip().split()
    return " ".join(words[:max_words]).strip()


class CaptionAgent:
    async def generate(
        self,
        scenario: str,
        emotion: str,
        mode: str,
        memory_examples: str = "",
    ) -> dict[str, str]:
        scen = (scenario or "").strip()
        emo = (emotion or "").strip().lower()
        m = (mode or MemeMode.PERSONAL).strip().lower()
        if m not in MemeMode.ALL:
            m = MemeMode.PERSONAL
        hint = _MODE_HINTS[m]
        mem = (memory_examples or "").strip()

        if settings.openai_api_key and scen:
            try:
                payload: dict[str, Any] = {
                    "scenario": scen[:8000],
                    "emotion": emo,
                    "mode": m,
                    "mode_hint": hint,
                }
                if mem:
                    payload["memory_examples"] = mem[:6000]
                data = await chat_json(
                    _CAPTION_GEN_SYSTEM,
                    json.dumps(payload),
                )
                return self._normalize_caption(data)
            except Exception:
                pass

        return self._mock_caption(scen, emo, m)

    def _normalize_caption(self, data: dict[str, Any]) -> dict[str, str]:
        top = _clamp_line(str(data.get("top_text", "")).strip(), 12)
        bottom = _clamp_line(str(data.get("bottom_text", "")).strip(), 12)
        if not top and not bottom:
            return self._mock_caption("", "", MemeMode.PERSONAL)
        return {
            "top_text": top[:200],
            "bottom_text": bottom[:200],
        }

    def _mock_caption(self, scenario: str, emotion: str, mode: str) -> dict[str, str]:
        words = scenario.split()
        slice_a = " ".join(words[:6]) if words else "wrong window right audience"
        slice_b = " ".join(words[6:12]) if len(words) > 6 else emotion or "same script"
        if mode == MemeMode.ROAST:
            top, bot = f"bold move {slice_a}", f"timeline archived {slice_b}"
        elif mode == MemeMode.DECISION:
            top, bot = f"door a {slice_a}", f"door b whispers {slice_b}"
        else:
            top, bot = f"same habit {slice_a}", f"new angle {slice_b}"
        return {
            "top_text": _clamp_line(top, 12),
            "bottom_text": _clamp_line(bot, 12),
        }
