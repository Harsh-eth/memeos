import json
from typing import Any

from backend.config import settings
from backend.services.llm import chat_json


CAPTION_SYSTEM = """You are the MemeOS Caption Agent. Output ONLY valid JSON:
{"top_text": "...", "bottom_text": "..."}
Rules:
- Short punchy lines; ALL CAPS optional for classic memes.
- Match the requested tone: funny (playful), savage (roast), dark (edgy but not illegal), genz (brainrot / ironic).
- For drake or two_panel: top_text = first panel / rejected or "before"; bottom_text = second / approved or "after".
- Keep each line under 120 chars. No hashtags unless genz and subtle.
"""


class CaptionAgent:
    async def captions(self, plan: dict[str, Any], user_prompt: str) -> dict[str, str]:
        if settings.openai_api_key:
            try:
                data = await chat_json(
                    CAPTION_SYSTEM,
                    json.dumps(
                        {
                            "user_prompt": user_prompt,
                            "plan": plan,
                        }
                    ),
                )
                return {
                    "top_text": str(data.get("top_text", "TOP")).strip()[:200],
                    "bottom_text": str(data.get("bottom_text", "BOTTOM")).strip()[:200],
                }
            except Exception:
                pass
        return self._mock_captions(plan, user_prompt)

    def _mock_captions(self, plan: dict[str, Any], user_prompt: str) -> dict[str, str]:
        topic = (plan.get("topic") or user_prompt or "life")[:40]
        tone = plan.get("tone", "funny")
        return {
            "top_text": f"WHEN {topic.upper()}",
            "bottom_text": f"{tone.upper()} MODE: {topic.upper()}",
        }
