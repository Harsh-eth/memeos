import hashlib
import json
from typing import Any

from config import settings
from services.llm import chat_json


PLANNER_SYSTEM = """You are the MemeOS Planner Agent. Given a user intent, output ONLY valid JSON with keys:
topic (string, concise meme subject),
tone (one of: funny, savage, dark, genz),
template_type (one of: drake, classic, two_panel — drake for preference memes, classic for top/bottom impact font style, two_panel for before/after or contrast),
style (short visual vibe, e.g. "bold ironic", "minimal chaos").
No markdown, no extra keys."""


class PlannerAgent:
    async def plan(self, user_prompt: str) -> dict[str, Any]:
        if settings.openai_api_key:
            try:
                data = await chat_json(
                    PLANNER_SYSTEM,
                    f'User intent: """{user_prompt}"""',
                )
                return self._normalize(data, user_prompt)
            except Exception:
                pass
        return self._mock_plan(user_prompt)

    def _normalize(self, data: dict[str, Any], user_prompt: str) -> dict[str, Any]:
        tone = str(data.get("tone", "funny")).lower()
        if tone not in {"funny", "savage", "dark", "genz"}:
            tone = "funny"
        tt = str(data.get("template_type", "classic")).lower()
        if tt not in {"drake", "classic", "two_panel"}:
            tt = "classic"
        return {
            "topic": str(data.get("topic", user_prompt))[:200],
            "tone": tone,
            "template_type": tt,
            "style": str(data.get("style", "internet meme"))[:120],
        }

    def _mock_plan(self, user_prompt: str) -> dict[str, Any]:
        h = int(hashlib.sha256(user_prompt.encode()).hexdigest(), 16)
        tones = ["funny", "savage", "dark", "genz"]
        templates = ["drake", "classic", "two_panel"]
        return {
            "topic": user_prompt[:160] or "nothing",
            "tone": tones[h % 4],
            "template_type": templates[(h // 4) % 3],
            "style": "mock offline planner",
        }
