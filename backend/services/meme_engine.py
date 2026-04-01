from __future__ import annotations

from collections import Counter, defaultdict, deque
from typing import Any

from agents.mode import MemeMode
from agents.replicate_llm import generate_meme_text
from services.memory_store import MemoryStore

_memory = MemoryStore()
_structure_counts: dict[str, Counter[str]] = defaultdict(Counter)
_recent_structures: dict[str, deque[str]] = defaultdict(lambda: deque(maxlen=5))


def _normalize_mode(mode: str | None) -> str:
    if not mode:
        return MemeMode.PERSONAL
    m = mode.strip().lower()
    return m if m in MemeMode.ALL else MemeMode.PERSONAL


def _detect_structure(top: str, bottom: str) -> str:
    t = (top or "").strip().lower()
    b = (bottom or "").strip().lower()

    if ("expectation" in t and "reality" in b) or ("expectation" in b and "reality" in t):
        return "expectation vs reality"

    if " vs " in t or " vs " in b or "vs." in t or "vs." in b:
        return "comparison"

    if t.startswith("me") and b.startswith("me"):
        return "self hypocrisy"

    if ":" in t or ":" in b:
        return "setup → punchline"

    return "default"


def _structure_hint_for_mode(mode: str) -> str:
    c = _structure_counts.get(mode)
    if not c:
        return ""
    top = c.most_common(1)
    if not top:
        return ""
    return top[0][0]


def _dominant_structure(mode: str) -> str:
    recent = _recent_structures.get(mode)
    if not recent:
        return ""
    c = Counter(recent)
    struct, n = c.most_common(1)[0]
    return struct if n >= 3 else ""


def _score_meme(top: str, bottom: str, structure: str) -> int:
    score = 6
    tw = len((top or "").split())
    bw = len((bottom or "").split())

    if tw <= 8 and bw <= 8:
        score += 1

    tset = set((top or "").lower().split())
    bset = set((bottom or "").lower().split())
    if tset and bset:
        overlap = len(tset & bset) / max(1, min(len(tset), len(bset)))
        if overlap <= 0.5:
            score += 1

    if structure != "default":
        score += 1

    return max(6, min(10, score))


def _examples_block(mode: str) -> str:
    mem = _memory.get_top(mode, limit=3)
    if not mem:
        return ""

    lines: list[str] = []
    for m in mem:
        caps = m.get("captions") if isinstance(m.get("captions"), dict) else {}
        top = str(caps.get("top_text", "")).strip()
        bottom = str(caps.get("bottom_text", "")).strip()
        if not top and not bottom:
            continue
        lines.append(f"Top: {top}")
        lines.append(f"Bottom: {bottom}")
        lines.append("")

    block = "\n".join(lines).strip()
    if not block:
        return ""
    return f"Examples of good memes:\n{block}"


async def run_meme_engine(topic: str, mode: str = MemeMode.PERSONAL) -> dict[str, Any]:
    m = _normalize_mode(mode)

    examples = _examples_block(m)
    dominant = _dominant_structure(m)
    structure_hint = dominant or _structure_hint_for_mode(m)

    data = await generate_meme_text(
        topic,
        m,
        examples=examples,
        structure_hint=structure_hint,
        force_structure=bool(dominant),
    )

    top_text = str(data.get("top_text", "")).strip()
    bottom_text = str(data.get("bottom_text", "")).strip()
    structure = _detect_structure(top_text, bottom_text)
    score = _score_meme(top_text, bottom_text, structure)

    meme_type = str(data.get("meme_type", "original") or "original").strip().lower()
    if meme_type not in ("template", "original"):
        meme_type = "original"
    template_name = data.get("template_name", None)
    if not (isinstance(template_name, str) and template_name.strip()):
        template_name = None
    image_search_query = str(data.get("image_search_query", "") or "").strip()
    image_idea = str(data.get("image_idea", "") or "").strip()

    _structure_counts[m][structure] += 1
    _recent_structures[m].append(structure)
    _memory.add(
        {
            "user_prompt": topic,
            "captions": {"top_text": top_text, "bottom_text": bottom_text},
            "mode": m,
            "structure": structure,
            "score": score,
            "meme_type": meme_type,
            "template_name": template_name,
        }
    )

    return {
        "scenario": str(data["scenario"]).strip(),
        "captions": {
            "top_text": top_text,
            "bottom_text": bottom_text,
        },
        "mode": m,
        "emotion": "neutral",
        "structure": structure,
        "score": score,
        "meme_type": meme_type,
        "template_name": template_name,
        "image_search_query": image_search_query,
        "image_idea": image_idea,
    }
