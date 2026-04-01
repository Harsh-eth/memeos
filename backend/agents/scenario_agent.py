from __future__ import annotations

import hashlib

from backend.agents.mode import MemeMode
from backend.config import settings
from backend.services.llm import chat_json

_BASE_RULES = """
Output ONLY valid JSON with a single key:
{"scenario": "<string>"}

The string must be EXACTLY ONE English sentence (one period at the end, no line breaks).
That single sentence must still spell out a clear sequence of beats using "First, … then, … finally, …" or numbered clauses inside the same sentence.

Mandatory content:
- Include a concrete mistake or tension (what could go wrong / what already went wrong).
- Include action plus consequence (someone does X and Y happens).
- Must feel like believable real-user behavior, not a fairy tale or abstract parable.

Be concrete (who/where/what); avoid vague filler like "something happened", "you know how it is", "typical day", or "little did they know".
""".strip()

_PROMPTS: dict[str, str] = {
    MemeMode.PERSONAL: f"""You are the MemeOS Scenario Agent — PERSONAL mode.
{_BASE_RULES}
Bias: realistic, relatable everyday situation the reader recognizes in themselves.""",
    MemeMode.ROAST: f"""You are the MemeOS Scenario Agent — ROAST mode.
{_BASE_RULES}
Bias: exaggerate mistakes, ironic bad decisions, and self-inflicted chaos — sharp but not slurs/targeted harassment.""",
    MemeMode.DECISION: f"""You are the MemeOS Scenario Agent — DECISION mode.
{_BASE_RULES}
Bias: frame the topic as a forks-in-the-road moment — options, pressure, and stakes in one sentence.""",
}


_MEMORY_TAIL = (
    "\n\nHere are examples of high-performing memes in this mode. "
    "Do not copy them, but follow their style (rhythm, specificity, punch)."
)


class ScenarioAgent:
    async def generate(self, topic: str, mode: str, memory_examples: str = "") -> str:
        t = (topic or "").strip()
        m = (mode or MemeMode.PERSONAL).strip().lower()
        if m not in MemeMode.ALL:
            m = MemeMode.PERSONAL

        if not t:
            return self._mock_scenario("(empty topic)", m)

        mem = (memory_examples or "").strip()
        user_msg = f'Topic:\n"""{t[:4000]}"""'
        if mem:
            user_msg = f"{user_msg}{_MEMORY_TAIL}\n\n{mem[:6000]}"

        system = _PROMPTS[m]
        if settings.openai_api_key:
            try:
                data = await chat_json(
                    system,
                    user_msg,
                )
                raw = data.get("scenario")
                if raw is not None:
                    out = str(raw).strip().split("\n")[0].strip()
                    if out:
                        if not out.endswith("."):
                            out = out[:799] + "."
                        return out[:800]
            except Exception:
                pass

        return self._mock_scenario(t, m)

    def _mock_scenario(self, topic: str, mode: str) -> str:
        h = int(hashlib.sha256(f"{topic}:{mode}".encode("utf-8")).hexdigest(), 16)
        fragments = {
            MemeMode.PERSONAL: (
                "First, you queue {topic} like it owns you, then the one detail you ignored shows up in public, "
                "and finally you laugh because the pattern is painfully familiar."
            ),
            MemeMode.ROAST: (
                "First, you turn {topic} into a flex, then the timeline preserves every hot take, "
                "and finally you blame the algorithm instead of the send button."
            ),
            MemeMode.DECISION: (
                "First, two doors open on {topic}, then the cheap option humiliates you on a delay, "
                "and finally you pretend the delay was the plan all along."
            ),
        }
        frag = fragments.get(mode, fragments[MemeMode.PERSONAL])
        short = (topic[:100] + "…") if len(topic) > 100 else (topic or "the choice")
        return frag.format(topic=short)
