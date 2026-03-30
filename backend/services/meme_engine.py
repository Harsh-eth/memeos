from __future__ import annotations

import io
import json
import re
from collections import Counter
from typing import Any

from PIL import Image

from agents.caption_agent import CaptionAgent
from agents.emotion_agent import EmotionAgent
from agents.mode import MemeMode
from agents.renderer import RendererAgent
from agents.scenario_agent import ScenarioAgent
from agents.score_agent import ScoreAgent
from agents.template_agent import TemplateAgent
from config import settings
from services.memory_store import MemoryStore

memory_store = MemoryStore()

_scenario_agent = ScenarioAgent()
_emotion_agent = EmotionAgent()
_caption_agent = CaptionAgent()
_score_agent = ScoreAgent()
_template_agent = TemplateAgent()
_renderer = RendererAgent()


def _template_catalog() -> list[dict[str, Any]]:
    root = settings.templates_dir
    idx = root / "index.json"
    if not idx.is_file():
        return []
    raw = json.loads(idx.read_text(encoding="utf-8"))
    out: list[dict[str, Any]] = []
    for item in raw.get("templates", []):
        path = root / item["path"]
        if not path.is_file():
            continue
        out.append({**item, "abs_path": str(path.resolve())})
    return out


def _resolve_template_dict(template_name: str) -> dict[str, Any]:
    """Map logical template id to a loaded template record; fallback if asset missing."""
    catalog = _template_catalog()
    if not catalog:
        raise FileNotFoundError(
            "No templates loaded. Run: python scripts/seed_templates.py from the backend folder."
        )
    name = (template_name or "").strip()
    for entry in catalog:
        if entry.get("name") == name:
            return dict(entry)
    for fallback in ("classic", "drake", "two_panel"):
        for entry in catalog:
            if entry.get("name") == fallback:
                return dict(entry)
    return dict(catalog[0])


_GENERIC_SNIPPETS = (
    "when you",
    "that moment",
    "be like",
)


def _line_has_generic_phrase(s: str) -> bool:
    low = s.lower()
    return any(g in low for g in _GENERIC_SNIPPETS)


def _excessive_word_repetition(text: str) -> bool:
    words = [w.lower() for w in re.findall(r"\b\w+\b", text) if len(w) > 2]
    if len(words) < 3:
        return False
    top = Counter(words).most_common(1)[0][1]
    return top >= 3


def _captions_invalid(caps: dict[str, Any]) -> bool:
    top = str(caps.get("top_text", "")).strip()
    bottom = str(caps.get("bottom_text", "")).strip()
    if len(top) < 5 or len(bottom) < 5:
        return True
    if _line_has_generic_phrase(top) or _line_has_generic_phrase(bottom):
        return True
    if _excessive_word_repetition(top) or _excessive_word_repetition(bottom):
        return True
    return False


def _normalize_mode(mode: str | None) -> str:
    m = (mode or MemeMode.PERSONAL).strip().lower()
    return m if m in MemeMode.ALL else MemeMode.PERSONAL


def _build_memory_text(mode: str) -> str:
    top_memes = memory_store.get_top(mode, 3)
    if not top_memes:
        return ""
    lines: list[str] = []
    for mem in top_memes:
        c = mem.get("captions")
        if not isinstance(c, dict):
            continue
        lines.append(
            "Example:\n"
            f"Top: {c.get('top_text', '')}\n"
            f"Bottom: {c.get('bottom_text', '')}\n"
        )
    return "".join(lines).strip()


async def _one_caption_candidate(
    scenario: str, emotion: str, m: str, memory_examples: str
) -> dict[str, str]:
    c = await _caption_agent.generate(scenario, emotion, m, memory_examples)
    if _captions_invalid(c):
        c = await _caption_agent.generate(scenario, emotion, m, memory_examples)
    return c


async def _render_best(
    scenario: str,
    emotion: str,
    captions: dict[str, str],
    template_id: str,
    m: str,
    best_score: int,
) -> tuple[bytes, dict[str, Any]]:
    tpl = _resolve_template_dict(template_id)
    try:
        raw_png = _renderer.render(tpl, captions["top_text"], captions["bottom_text"])
    except OSError as e:
        raise FileNotFoundError(str(e)) from e

    im = Image.open(io.BytesIO(raw_png)).convert("RGB")
    im = im.resize(
        (settings.meme_output_width, settings.meme_output_height),
        Image.Resampling.LANCZOS,
    )
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    image_bytes = buf.getvalue()

    metadata: dict[str, Any] = {
        "scenario": scenario,
        "emotion": emotion,
        "captions": captions,
        "template": template_id,
        "mode": m,
        "score": best_score,
    }
    return image_bytes, metadata


async def _run_engine_attempt(
    topic: str, m: str, *, allow_scenario_rerun: bool
) -> tuple[bytes, dict[str, Any]]:
    memory_text = _build_memory_text(m)
    scenario = await _scenario_agent.generate(topic, m, memory_text)
    emotion = await _emotion_agent.detect(scenario)

    candidates: list[dict[str, str]] = []
    for _ in range(2):
        candidates.append(
            await _one_caption_candidate(scenario, emotion, m, memory_text)
        )

    best: dict[str, str] | None = None
    best_score = -1
    for c in candidates:
        s = await _score_agent.score(scenario, c)
        if s > best_score:
            best_score = s
            best = c

    if best is None:
        best = candidates[-1]
        best_score = max(best_score, 1)

    if best_score < 6 and allow_scenario_rerun:
        return await _run_engine_attempt(topic, m, allow_scenario_rerun=False)

    if best_score >= 6 and best is not None:
        memory_store.add(
            {
                "topic": topic,
                "scenario": scenario,
                "emotion": emotion,
                "captions": dict(best),
                "score": best_score,
                "mode": m,
            }
        )

    template_id = _template_agent.select(emotion)
    return await _render_best(scenario, emotion, best, template_id, m, best_score)


async def run_meme_engine(
    topic: str, mode: str = MemeMode.PERSONAL
) -> tuple[bytes, dict[str, Any]]:
    m = _normalize_mode(mode)
    return await _run_engine_attempt(topic, m, allow_scenario_rerun=True)
