from __future__ import annotations

import asyncio
import json
import random
import re

import httpx
import replicate

from config import settings

client = replicate.Client(api_token=settings.REPLICATE_API_TOKEN)

_IMGFLIP_TOP_CACHE: list[dict[str, str]] | None = None
_IMGFLIP_TOP_CACHE_AT: float = 0.0


_TEMPLATE_USE_CASES: dict[str, str] = {
    "drake hotline bling": "reject one thing, prefer another",
    "two buttons": "choosing between two options / dilemma",
    "distracted boyfriend": "ignoring current thing for something more attractive",
    "expanding brain": "progression from basic to absurd ideas",
    "crying wojak": "sad, regret, self-deprecating emotion",
}


def _candidate_by_lower(allowed_names: set[str], want_lower: str) -> str | None:
    wl = (want_lower or "").strip().lower()
    if not wl:
        return None
    for n in allowed_names:
        if n.strip().lower() == wl:
            return n
    return None


def _classify_structure(text: str) -> dict[str, bool]:
    t = (text or "").strip().lower()
    if not t:
        return {"comparison": False, "decision": False, "temptation": False, "regret": False, "hypocrisy": False}

    # Hard cues
    has_contrast = (" vs " in t) or ("vs." in t) or (" versus " in t) or (" instead " in t) or (" rather " in t)
    has_or = " or " in t

    decision_kw = (
        "should i",
        "choose",
        "choice",
        "decide",
        "decision",
        "pick",
        "dilemma",
    )
    preference_kw = ("better", "worse", "prefer", "favorite", "over ", "more than")
    temptation_kw = ("tempt", "crush", "new thing", "shiny", "distract", "ignoring", "ignores", "left my", "cheat")
    regret_kw = ("regret", "sad", "depress", "missed", "ashamed", "embarrass", "cringe", "pathetic")
    hypocrisy_kw = ("pretend", "pretending", "delusion", "lying to myself", "cope", "i swear i'm", "i'm locked in")

    is_comparison = has_contrast or any(k in t for k in preference_kw)
    is_decision = has_or or any(k in t for k in decision_kw)
    is_temptation = any(k in t for k in temptation_kw)
    is_regret = any(k in t for k in regret_kw)
    is_hypocrisy = any(k in t for k in hypocrisy_kw)

    return {
        "comparison": is_comparison,
        "decision": is_decision,
        "temptation": is_temptation,
        "regret": is_regret,
        "hypocrisy": is_hypocrisy,
    }


_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\s*(am|pm)\b", re.IGNORECASE)
_REPEAT_RE = re.compile(r"\b(x\d+|\d{2,}\s*times|\d{3,})\b", re.IGNORECASE)


def _is_high_confidence_meme(topic: str) -> bool:
    """
    High-confidence meme structures that should almost always be template-worthy.
    Signals:
      - time-based escalation (2:47am, sunrise, etc.)
      - "one more" behavior
      - repetition loops (again, x10, 847 times)
      - intention vs reality / contrast
    """
    t = (topic or "").strip().lower()
    if not t:
        return False
    if _TIME_RE.search(t):
        return True
    if any(x in t for x in ("sunrise", "sun's up", "birds chirp", "3am", "2am", "4am")):
        return True
    if any(x in t for x in ("one more", "just one more", "one last", "last one")):
        return True
    if "again" in t or _REPEAT_RE.search(t):
        return True
    # intention vs reality / contrast markers
    if any(x in t for x in (" vs ", "vs.", "versus", "instead", "but then", "and then", "until")):
        return True
    if ("alarm" in t and any(x in t for x in ("snooze", "noon", "2:", "3:", "4:"))):
        return True
    return False


def _pick_high_confidence_template(allowed_names: set[str], topic: str) -> str | None:
    """
    Template priority for high-confidence meme patterns.
    - "one more video" → Drake or Two Buttons
    - "last time" / regret → Crying Wojak or Drake
    - "before bed" → Drake
    - repetition loops → Drake or Expanding Brain
    """
    t = (topic or "").strip().lower()
    c = _classify_structure(topic)

    # explicit patterns first
    if "before bed" in t:
        return _candidate_by_lower(allowed_names, "drake hotline bling") or _candidate_by_lower(
            allowed_names, "two buttons"
        )
    if any(x in t for x in ("one more", "just one more", "one last", "last one")):
        return _candidate_by_lower(allowed_names, "drake hotline bling") or _candidate_by_lower(
            allowed_names, "two buttons"
        )
    if "last time" in t or c["regret"]:
        return _candidate_by_lower(allowed_names, "crying wojak") or _candidate_by_lower(
            allowed_names, "drake hotline bling"
        )
    if "again" in t or _REPEAT_RE.search(t):
        return _candidate_by_lower(allowed_names, "drake hotline bling") or _candidate_by_lower(
            allowed_names, "expanding brain"
        )

    # fall back to our standard priority mapping
    return _rule_pick_template(allowed_names, topic)


def _rule_pick_template(allowed_names: set[str], topic: str) -> str | None:
    """
    Deterministic override to prevent shallow semantic misfires.
    Priority rules:
      - decision/conflict → Two Buttons (PRIMARY)
      - preference/better vs worse/comparison → Drake (PRIMARY)
      - distraction/temptation → Distracted Boyfriend
      - regret/sadness → Crying Wojak
      - hypocrisy/self-delusion → Clown Applying Makeup (LOW PRIORITY)
    """
    c = _classify_structure(topic)

    # Hard override: contrast words force Drake/Two Buttons.
    t = (topic or "").lower()
    hard_contrast = (" vs " in t) or ("vs." in t) or (" versus " in t) or (" instead " in t) or (" rather " in t) or (" or " in t)
    if hard_contrast:
        if c["decision"]:
            return _candidate_by_lower(allowed_names, "two buttons") or _candidate_by_lower(
                allowed_names, "drake hotline bling"
            )
        return _candidate_by_lower(allowed_names, "drake hotline bling") or _candidate_by_lower(
            allowed_names, "two buttons"
        )

    if c["decision"]:
        return _candidate_by_lower(allowed_names, "two buttons")
    if c["comparison"]:
        return _candidate_by_lower(allowed_names, "drake hotline bling")
    if c["temptation"]:
        return _candidate_by_lower(allowed_names, "distracted boyfriend")
    if c["regret"]:
        return _candidate_by_lower(allowed_names, "crying wojak")
    # Clown is explicitly low priority: only if hypocrisy AND no other structure.
    if c["hypocrisy"] and not (c["decision"] or c["comparison"] or c["temptation"] or c["regret"]):
        return _candidate_by_lower(allowed_names, "clown applying makeup")
    return None


async def _imgflip_top_templates(limit: int = 40) -> list[dict[str, str]]:
    """Fetch and cache top Imgflip templates (id+name+use_case)."""
    global _IMGFLIP_TOP_CACHE, _IMGFLIP_TOP_CACHE_AT  # noqa: PLW0603
    now = asyncio.get_event_loop().time()
    if _IMGFLIP_TOP_CACHE and (now - _IMGFLIP_TOP_CACHE_AT) < 6 * 60 * 60:
        return _IMGFLIP_TOP_CACHE[:limit]

    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as http:
        r = await http.get("https://api.imgflip.com/get_memes")
        r.raise_for_status()
        data = r.json()
        if not data.get("success"):
            raise RuntimeError(f"imgflip get_memes failed: {data}")
        memes = (data.get("data") or {}).get("memes") or []
        out: list[dict[str, str]] = []
        for m in memes:
            if not isinstance(m, dict):
                continue
            mid = str(m.get("id") or "").strip()
            name = str(m.get("name") or "").strip()
            if not mid or not name:
                continue
            use_case = _TEMPLATE_USE_CASES.get(name.strip().lower(), "")
            out.append({"id": mid, "name": name, "use_case": use_case})
            if len(out) >= max(50, limit):
                break
        _IMGFLIP_TOP_CACHE = out
        _IMGFLIP_TOP_CACHE_AT = now
        return out[:limit]


def _build_tone_instruction(mode: str) -> str:
    if mode == "roast":
        return """
Tone: savage, sarcastic, slightly offensive but funny.
Make the caption feel like a brutal truth.
Short punchlines. No safe language.
"""
    elif mode == "decision":
        return """
Tone: conflicted, ironic, relatable internal debate.
Make it feel like overthinking or bad decision making.
"""
    else:
        return """
Tone: personal, relatable, emotional.
Feels like "this is literally me".
"""


def _extract_json(text: str) -> str:
    t = (text or "").strip()

    if t.startswith("```"):
        parts = t.split("```")
        if len(parts) >= 2:
            t = parts[1].strip()

    if t.lower().startswith("json"):
        lines = t.splitlines()
        if len(lines) > 1:
            t = "\n".join(lines[1:]).strip()

    if t.startswith("{") and t.endswith("}"):
        return t

    l = t.find("{")
    r = t.rfind("}")
    if l != -1 and r != -1 and r > l:
        return t[l : r + 1].strip()

    return t


def _is_generic_phrase(s: str) -> bool:
    t = (s or "").strip().lower()
    if not t:
        return True
    bad = (
        "that moment",
        "when you",
        "when u",
        "me when",
        "pov",
        "relatable",
        "so true",
        # overly explainy / safe tone
        "like a responsible adult",
        "because i deserve it",
    )
    return any(x in t for x in bad)


def _too_long(text: str, *, max_words: int = 10) -> bool:
    return len((text or "").strip().split()) > max_words


def _token_overlap(a: str, b: str) -> float:
    sa = {w for w in (a or "").lower().split() if w}
    sb = {w for w in (b or "").lower().split() if w}
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    denom = max(1, min(len(sa), len(sb)))
    return inter / denom


def _has_punch(s: str) -> bool:
    t = (s or "").strip()
    if not t:
        return False
    if any(p in t for p in ("!", "?", "…")):
        return True
    lo = t.lower()
    if any(x in lo for x in ("but", "then", "until", "instead", "and now")):
        return True
    last = lo.split()[-1] if lo.split() else ""
    return len(last) >= 5


def _captions_ok(top: str, bottom: str) -> bool:
    t = (top or "").strip()
    b = (bottom or "").strip()
    if not t or not b:
        return False
    if _too_long(t) or _too_long(b):
        return False
    if _is_generic_phrase(t) or _is_generic_phrase(b):
        return False
    if t.strip().lower() == b.strip().lower():
        return False
    if _token_overlap(t, b) >= 0.75:
        return False
    if not _has_punch(b):
        return False
    return True


def _sharpen_caption(s: str) -> str:
    """
    Make captions shorter + more internet-native.
    - lowercase by default
    - remove explainy filler
    - hard cap words (keep the funniest core)
    """
    t = (s or "").strip()
    if not t:
        return ""

    # normalize punctuation/quotes
    t = t.replace("“", '"').replace("”", '"').replace("’", "'")
    t = t.strip().strip('"').strip("'").strip()

    # lowercase default (internet tone)
    t = t.lower()

    # ban/strip explainy phrases
    banned_substrings = (
        "like a responsible adult",
        "because i deserve it",
        "for real",
        "actually",
        "literally",
        "at this point",
        "in my head",
    )
    for b in banned_substrings:
        t = t.replace(b, "")

    # compress common fluff
    replacements = {
        "i will": "i'll",
        "i am": "i'm",
        "i have": "i've",
        "going to": "gonna",
        "want to": "wanna",
        "trying to": "tryna",
        "kind of": "kinda",
        "sort of": "kinda",
        "a lot of": "mad",
        "very": "",
        "really": "",
        "just": "",
        "that": "",
        "this month": "",
        "right now": "",
    }
    for a, b in replacements.items():
        t = t.replace(a, b)

    # encourage meme voice
    t = t.replace("i ", "me ", 1) if t.startswith("i ") else t

    # collapse whitespace
    t = " ".join(t.split())

    # avoid trailing periods (feels like explaining)
    t = t.rstrip(".")
    return t.strip()


def _has_edge(s: str) -> bool:
    t = (s or "").strip().lower()
    if not t:
        return False
    # specificity: digits / timestamps / years
    if any(ch.isdigit() for ch in t):
        return True
    if "am" in t or "pm" in t:
        return True
    # micro-surprise / meme-native tags
    if any(x in t for x in ("for no reason", "again", "like always", "this app", "my brain", "side quest")):
        return True
    # exaggeration / absurdity keywords
    if any(x in t for x in ("every single time", "47 hours", "a million", "npc", "side quests")):
        return True
    return False


def _cap_words(s: str, n: int = 10) -> str:
    w = (s or "").strip().split()
    return " ".join(w[:n]).strip()


def _cap_words_tail(s: str, n: int = 10) -> str:
    w = (s or "").strip().split()
    if len(w) <= n:
        return " ".join(w).strip()
    return " ".join(w[-n:]).strip()


def _ban_generic_caption(s: str, *, fallback: str) -> str:
    t = (s or "").strip().lower()
    if not t:
        return fallback
    # avoid ultra-generic meme cores
    generic_exact = {
        "saving money",
        "working hard",
        "being productive",
        "me saving money",
        "me working hard",
        "me being productive",
    }
    if t in generic_exact:
        return fallback
    return s


def _edgeify_pair(topic: str, top: str, bottom: str) -> tuple[str, str]:
    """
    Enforce:
      - at least one of (specificity/exaggeration/absurdity)
      - bottom line feels like escalation/twist
      - micro surprise token present somewhere when possible
    """
    t = (top or "").strip()
    b = (bottom or "").strip()

    # Ban generic lines by swapping in more specific defaults.
    t = _ban_generic_caption(t, fallback="me opening my banking app")
    b = _ban_generic_caption(b, fallback="checking out anyway... like always")

    # Ensure bottom reads like escalation (cheap but effective).
    b_lo = b.lower()
    if not any(x in b_lo for x in ("but", "then", "and now", "until", "...")):
        # Keep the twist short so it survives word-capping.
        b = f"{b} ... sun's up"

    # Ensure at least one edge element exists across top/bottom.
    if not (_has_edge(t) or _has_edge(b)):
        # Prefer adding specificity to bottom; keep it short.
        b = f"{b} at 2:57am"

    # Add micro-surprise token if still missing.
    if not any(
        x in (t.lower() + " " + b.lower()) for x in ("for no reason", "again", "like always", "this app")
    ):
        # append to bottom (usually funnier)
        b = f"{b} again"

    # Re-cap length after injections.
    t = _cap_words(_sharpen_caption(t), 10)
    # Bottom should preserve the twist; keep the tail.
    b = _cap_words_tail(_sharpen_caption(b), 10)
    return t, b


def _image_idea_ok(s: str) -> bool:
    t = (s or "").strip().lower()
    if not t:
        return False
    # Ban vague / abstract phrasing
    banned = (
        "thinking about life",
        "thinking",
        "person thinking",
        "feeling",
        "emotion",
        "vibes",
        "aesthetic",
        "abstract",
        "concept",
        "symbolic",
    )
    if any(x in t for x in banned):
        return False
    # Must include subject + action + environment-ish cue
    words = [w for w in t.replace(",", " ").split() if w]
    if len(words) < 7:
        return False
    has_subject = any(w in words for w in ("guy", "girl", "man", "woman", "student", "friend", "dad", "mom", "person"))
    has_action = any(w in words for w in ("scrolling", "staring", "holding", "sitting", "lying", "walking", "typing", "arguing", "crying", "laughing", "texting", "checking"))
    has_env = any(w in words for w in ("room", "bed", "desk", "couch", "kitchen", "bus", "train", "street", "bathroom", "office", "class", "night", "morning"))
    return has_subject and has_action and has_env


def _coerce_image_idea(scenario: str, image_idea: str) -> str:
    """
    Ensures: subject + action + environment.
    We keep it short and internet-real; no cinematic adjectives.
    """
    scen = (scenario or "").strip()
    idea = (image_idea or "").strip()
    if _image_idea_ok(idea):
        return idea
    base = (scen or "having a bad day").strip()
    subject = random.choice(["guy", "girl", "person", "student"])
    action = random.choice(["scrolling phone", "staring at laptop", "lying on bed", "checking messages"])
    environment = random.choice(["messy room", "dark room", "cluttered desk", "bedroom at night"])
    # One sentence, realistic, short.
    tail = base.lower()
    if tail.endswith("."):
        tail = tail[:-1]
    tail = tail[:90].strip()
    return f"{subject} {action} in a {environment}, {tail}"


def _infer_template_from_topic(topic: str) -> str | None:
    t = (topic or "").strip().lower()
    if not t:
        return None
    # Mandatory mapping rules (cheap keyword heuristics) → return REAL meme names
    if any(x in t for x in ("good vs", "bad vs", "good or", "bad or", "should i", "choice", "choose", "decision")):
        return "drake hotline bling"
    if any(x in t for x in ("sleep", "scroll", "scrolling", "screen time", "phone", "doomscroll", "laziness", "lazy")):
        return "two buttons"
    if "expectation" in t and "reality" in t:
        return "two buttons"
    if " vs " in t or "vs." in t or "compare" in t or "comparison" in t:
        return "distracted boyfriend"
    if any(x in t for x in ("progression", "escalat", "level up", "galaxy brain", "evolving")):
        return "expanding brain"
    if any(x in t for x in ("sad", "depress", "pathetic", "embarrass", "cringe", "self-deprec")):
        return "crying wojak"
    return None


async def generate_meme_text(
    topic: str,
    mode: str,
    *,
    examples: str = "",
    structure_hint: str = "",
    force_structure: bool = False,
) -> dict:
    tone_block = _build_tone_instruction(mode)
    templates = await _imgflip_top_templates(40)
    allowed_names = {t["name"] for t in templates if isinstance(t, dict) and t.get("name")}
    templates_json = json.dumps(templates, ensure_ascii=False)

    examples_block = f"{examples}\n\n" if examples else ""
    if structure_hint and force_structure:
        structure_block = f"Structure:\nYou MUST follow a {structure_hint} format.\n\n"
    else:
        structure_block = (
            f"Structure hint:\nUse a {structure_hint} format.\n\n" if structure_hint else ""
        )

    prompt = f"""
You are a meme planner. From a user prompt, output ONE strict JSON object with:
- scenario (short real-life situation)
- captions (top_text, bottom_text)
- meme_type decision (template vs original)
- template selection OR an original image idea
- image_search_query for templates (NO captions in query)

{tone_block}

Return EXACT JSON with these keys and types:
{{
  "scenario": "short real-life situation",
  "top_text": "top caption",
  "bottom_text": "bottom caption",
  "meme_type": "template" | "original",
  "template_name": "natural meme template name" | null,
  "image_search_query": "clean search query for template image (optional)",
  "image_idea": "fallback scene if template not used"
}}

Rules:
- Template candidates (MANDATORY):
  Choose the BEST template based on meaning (use_case), from this list ONLY (no custom names):
  {templates_json}

- Output constraint:
  If meme_type == "template", template_name MUST be an exact "name" from the list above.
  If none fit well, set meme_type="original" and template_name=null.

- Decision rule:
  1) Understand the scenario.
  2) Match scenario to template use_case.
  3) Select the best template.

- Mandatory structure classification (answer internally before choosing):
  - Is this a comparison?
  - Is this a decision/conflict?
  - Is this temptation/distraction?
  - Is this regret/sadness?

- Template priority rules (STRICT):
  - decision / conflict → "Two Buttons" (PRIMARY)
  - preference / better vs worse → "Drake Hotline Bling" (PRIMARY)
  - distraction / temptation → "Distracted Boyfriend"
  - regret / sadness → "Crying Wojak"
  - self-irony / hypocrisy → "Clown Applying Makeup" (LOW PRIORITY)

- Limit Clown Applying Makeup (STRICT):
  - ONLY use if the joke is about pretending / self-delusion / hypocrisy
  - AND no decision or comparison structure exists

- STRICT DECISION FLOW (template-first):
  1) Try to map the user prompt to a known meme format.
  2) If a mapping exists → meme_type MUST be "template".
  3) If NO mapping exists → meme_type MUST be "original".

- Default:
  - meme_type MUST default to "template".
  - Only choose "original" if NO template fits logically OR the scenario is highly specific and not template-friendly.

- Mandatory template mapping rules:
  - sleep / phone / scrolling / laziness → "two buttons" OR "drake hotline bling"
  - good vs bad choice → "drake hotline bling"
  - comparison between two things → "distracted boyfriend"
  - expectation vs reality → "two buttons"
  - progression / escalation → "expanding brain"
  - sad / self-deprecating → "crying wojak"

- ORIGINAL restriction (strict):
  - Only allow meme_type="original" if:
    - scenario is highly specific AND templates do not fit, OR
    - no template structure logically fits
- Mode ↔ template sanity:
  - roast: prefer sharper contrast formats ("drake hotline bling" / "expanding brain" / "crying wojak") ONLY if it fits perfectly
  - decision: prefer comparison/conflict ("distracted boyfriend" / "two buttons") ONLY if it fits perfectly
  - personal: prefer simple relatable formats ("drake hotline bling" / "two buttons") ONLY if it fits perfectly
  - if the mode-fit feels forced, choose a DIFFERENT template; only use "original" if no template fits at all
- TEMPLATE STRICTNESS (only if meme_type == "template"):
  - You MUST match the template structure exactly; if not a perfect fit, choose "original".
  - drake hotline bling: rejection vs preference (A is rejected, B is preferred)
  - two buttons: expectation vs reality / choice between two options
  - distracted boyfriend: comparison / temptation (A ignores current thing for new thing)
  - expanding brain: escalating ladder of takes (from normal → galaxy brain)
  - crying wojak: emotional breakdown / shame / regret (one-sided despair)
- Template selection:
  - template_name MUST be an exact name from the provided list (no custom names).
  - If meme_type == "template", template_name must be non-null and specific.
  - If meme_type == "original", template_name must be null.
- Image search query (templates only):
  - image_search_query must be a clean query like "drake meme template blank"
  - DO NOT include captions in image_search_query.
- Image idea (original only):
  - image_idea MUST be visual and specific; include: subject + environment + action
  - good: "guy lying in bed at night scrolling phone with messy blanket"
  - bad: "person thinking about life"
  - REQUIRED format: "subject + action + environment" (one sentence)
  - no artistic words, no cinematic language, no brand names if possible
- Caption ↔ image alignment:
  - the image must visually support the BOTTOM caption
  - avoid generic reaction images; make the action/environment do the storytelling
- Captions:
  - max 8–10 words per line
  - lowercase by default (unless a word is intentionally ALL CAPS for emphasis)
  - BAN generic meme openers: "when you", "that moment", "me when", "POV"
  - BAN explainy tone phrases: "like a responsible adult", "because i deserve it"
  - BAN generic cores: "saving money", "working hard", "being productive"
  - Bottom MUST be a twist/escalation (harder, more chaotic)
  - Add EDGE: include at least ONE of:
    - exaggeration (e.g. "47 hours", "every single time")
    - specificity (e.g. "2:57am", "3rd coffee", "2019 posts")
    - absurdity (e.g. "my brain doing side quests")
  - Add micro-surprise sometimes: "for no reason", "again", "like always", "this app"
  - DO NOT explain context; imply it
  - no full sentences unless necessary (fragments are better)
  - no repetition
  - tweet-worthy
  - strong contrast between top & bottom

Extra rules:
- Think in meme formats first, not essay writing.
- Tone: tweet-like, slightly chaotic, human.
- sound like a human, not AI
- if you're unsure, choose meme_type="original" and provide a strong image_idea

{examples_block}{structure_block}User topic:
{topic}
""".strip()

    def _run() -> str:
        output = client.run(
            "anthropic/claude-opus-4.6",
            input={
                "prompt": prompt,
                "max_tokens": 1024,
                "temperature": 0.8,
            },
        )
        if isinstance(output, str):
            return output
        try:
            return "".join(output).strip()
        except Exception:
            return str(output).strip()

    last: dict | None = None
    for _ in range(2):
        text = (await asyncio.to_thread(_run)).strip()
        data = json.loads(_extract_json(text))
        last = data
        top = _sharpen_caption(str(data.get("top_text", "")).strip())
        bottom = _sharpen_caption(str(data.get("bottom_text", "")).strip())
        top, bottom = _edgeify_pair(topic, top, bottom)

        meme_type = str(data.get("meme_type", "")).strip().lower()
        if meme_type not in ("template", "original"):
            meme_type = "original"

        template_name_raw = data.get("template_name", None)
        template_name = str(template_name_raw).strip() if isinstance(template_name_raw, str) else ""
        template_name = template_name.strip()
        if not template_name:
            template_name = None
        elif template_name not in allowed_names:
            template_name = None

        scenario = str(data.get("scenario", "")).strip()
        image_search_query = str(data.get("image_search_query", "")).strip()
        image_idea = str(data.get("image_idea", "")).strip()

        # High-confidence detector: prefer templates, avoid Flux fallbacks.
        high_conf = _is_high_confidence_meme(topic)
        forced = _pick_high_confidence_template(allowed_names, topic) if high_conf else _rule_pick_template(allowed_names, topic)
        if forced:
            meme_type = "template"
            template_name = forced
        elif high_conf:
            # If high-confidence but no specific pick found, default to Drake/Two Buttons if available.
            meme_type = "template"
            template_name = _candidate_by_lower(allowed_names, "drake hotline bling") or _candidate_by_lower(
                allowed_names, "two buttons"
            )

        # Extra clamp: Clown only allowed for hypocrisy/self-delusion and no decision/comparison.
        if template_name and template_name.strip().lower() == "clown applying makeup":
            cls = _classify_structure(topic)
            if not (cls["hypocrisy"] and not (cls["decision"] or cls["comparison"])):
                template_name = forced or None

        if meme_type == "template":
            if not template_name:
                inferred = _infer_template_from_topic(topic)
                if inferred:
                    # only if present in candidate list
                    for n in allowed_names:
                        if n.lower() == inferred.lower():
                            template_name = n
                            break
                else:
                    # For high confidence, do not drop to original; keep template and let pipeline try.
                    if not high_conf:
                        meme_type = "original"
                        template_name = None
        else:
            template_name = None
            image_search_query = ""

        # Template-first fallback: if Claude said original, try to infer a template mapping.
        if meme_type == "original":
            inferred = _infer_template_from_topic(topic)
            if inferred:
                for n in allowed_names:
                    if n.lower() == inferred.lower():
                        meme_type = "template"
                        template_name = n
                        image_search_query = n
                        break

        image_idea = _coerce_image_idea(scenario, image_idea)

        out = {
            "scenario": scenario,
            "top_text": top,
            "bottom_text": bottom,
            "meme_type": meme_type,
            "template_name": template_name,
            "image_search_query": image_search_query,
            "image_idea": image_idea,
        }

        if _captions_ok(top, bottom):
            return out

    if isinstance(last, dict):
        top = str(last.get("top_text", "")).strip()
        bottom = str(last.get("bottom_text", "")).strip()
        scenario = str(last.get("scenario", "")).strip()
        image_idea = _coerce_image_idea(scenario, str(last.get("image_idea", "")).strip())
        return {
            "scenario": scenario,
            "top_text": top,
            "bottom_text": bottom,
            "meme_type": "original",
            "template_name": None,
            "image_search_query": "",
            "image_idea": image_idea,
        }
    return {
        "scenario": "",
        "top_text": "",
        "bottom_text": "",
        "meme_type": "original",
        "template_name": None,
        "image_search_query": "",
        "image_idea": "person sitting at a messy desk, scrolling phone, tired at night",
    }

