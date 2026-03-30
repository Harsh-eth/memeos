from __future__ import annotations

import hashlib

from config import settings
from services.llm import chat_json

ALLOWED = (
    "regret",
    "denial",
    "overconfidence",
    "frustration",
    "delusion",
    "cope",
)

EMOTION_SYSTEM = f"""You are the MemeOS Emotion Agent. Output ONLY valid JSON with a single key:
{{"emotion": "<one word>"}}

The value must be exactly ONE word, lowercase, chosen from this closed set and nothing else:
{", ".join(ALLOWED)}

Pick the single label that best matches the dominant emotional posture implied by the scenario (how the subject is reacting or framing things, not a clinical diagnosis). No synonyms, no punctuation, no explanation."""


class EmotionAgent:
    async def detect(self, scenario: str) -> str:
        text = (scenario or "").strip()
        if not text:
            return self._mock_emotion(text)

        if settings.openai_api_key:
            try:
                data = await chat_json(
                    EMOTION_SYSTEM,
                    f'Scenario:\n"""{text[:8000]}"""',
                )
                raw = data.get("emotion")
                if raw is not None:
                    word = str(raw).strip().lower()
                    word = word.split()[0] if word else ""
                    if word in ALLOWED:
                        return word
            except Exception:
                pass

        return self._mock_emotion(text)

    def _mock_emotion(self, scenario: str) -> str:
        h = int(hashlib.sha256(scenario.encode("utf-8")).hexdigest(), 16)
        return ALLOWED[h % len(ALLOWED)]
