from __future__ import annotations

import io
from typing import Any

import asyncio
import random
import httpx
import replicate
from PIL import Image, ImageDraw, ImageFont
import logging
import time
import re

from backend.agents.mode import MemeMode
from backend.config import settings
from backend.services.meme_engine import run_meme_engine

FONT_PATH = "./Impact.ttf"
_tlog = logging.getLogger("memeos.template_debug")

# In-process debug counters (template hit rate)
_template_success = 0
_template_fail = 0

def validate_template_fit(template_name: str, top_text: str, bottom_text: str) -> bool:
    """
    Best-effort caption ↔ template validation to avoid mismatched templates.
    Keeps logic lightweight; if unsure, return False to fallback to original.
    """
    t = (top_text or "").strip().lower()
    b = (bottom_text or "").strip().lower()
    if not t or not b:
        return False
    name = (template_name or "").strip().lower()

    # shared signals
    tset = {w for w in t.replace("—", " ").replace("…", " ").split() if w}
    bset = {w for w in b.replace("—", " ").replace("…", " ").split() if w}
    overlap = (len(tset & bset) / max(1, min(len(tset), len(bset)))) if tset and bset else 0.0
    has_vs = (" vs " in t) or (" vs " in b) or ("vs." in t) or ("vs." in b)
    has_instead = ("instead" in t) or ("instead" in b)
    has_expect_reality = ("expectation" in t and "reality" in b) or ("expectation" in b and "reality" in t)
    setup_markers = ("when " in t) or ("trying to" in t) or ("i said" in t) or ("i will" in t) or (":" in t)
    outcome_markers = any(x in b for x in ("but", "then", "and now", "until", "reality", "actually", "ends up"))

    if name == "drake":
        # Drake is broadly usable; avoid false negatives that push Flux fallback.
        # If the planner chose drake and captions exist, accept.
        return True

    if name == "two_panel":
        # setup → outcome/reality
        return has_expect_reality or (setup_markers and outcome_markers)

    if name == "distracted_boyfriend":
        # comparison / temptation (A vs B)
        return has_vs or has_instead or ("new" in b) or ("better" in b)

    # others: allow, since we don't render multi-step templates here yet
    if name in ("expanding_brain", "crying_wojak"):
        return True

    return False


def draw_text_with_stroke(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    stroke_width: int = 2,
) -> None:
    x, y = position
    for dx in range(-stroke_width, stroke_width + 1):
        for dy in range(-stroke_width, stroke_width + 1):
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, font=font, fill="black")
    draw.text((x, y), text, font=font, fill="white")


def get_fitting_font(draw, text, max_width, start_size=60, min_size=18):
    for size in range(start_size, min_size, -2):
        try:
            font = ImageFont.truetype(FONT_PATH, size)
        except Exception:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            return font
    return ImageFont.load_default()


def wrap_text_limited(text, font, max_width, draw, max_lines=2):
    words = text.split()
    lines = []
    current = ""

    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        w = bbox[2] - bbox[0]

        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

        if len(lines) == max_lines - 1:
            break

    if current:
        lines.append(current)

    return lines[:max_lines]


def emphasize_words(text: str) -> str:
    words = text.split()

    if len(words) <= 3:
        return text.upper()

    # emphasize last impactful words
    for i in range(len(words) - 1, -1, -1):
        if len(words[i]) > 4:
            words[i] = words[i].upper()
            break

    return " ".join(words)


def render_meme(image_bytes: bytes, top_text: str, bottom_text: str) -> bytes:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)

    width, height = img.size
    max_width = int(width * 0.9)

    line_spacing = 6

    top_text = emphasize_words(top_text)
    bottom_text = emphasize_words(bottom_text)

    top_font = get_fitting_font(draw, top_text.upper(), max_width)
    bottom_font = get_fitting_font(draw, bottom_text.upper(), max_width)

    top_lines = wrap_text_limited(top_text.upper(), top_font, max_width, draw)
    y = 10
    for line in top_lines:
        bbox = draw.textbbox((0, 0), line, font=top_font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = (width - w) // 2
        draw_text_with_stroke(draw, (x, y), line, top_font)
        y += h + line_spacing

    bottom_lines = wrap_text_limited(bottom_text.upper(), bottom_font, max_width, draw)
    total_h = 0
    for line in bottom_lines:
        bbox = draw.textbbox((0, 0), line, font=bottom_font)
        total_h += (bbox[3] - bbox[1]) + line_spacing
    y = height - total_h - 10
    for line in bottom_lines:
        bbox = draw.textbbox((0, 0), line, font=bottom_font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = (width - w) // 2
        draw_text_with_stroke(draw, (x, y), line, bottom_font)
        y += h + line_spacing

    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


def add_source_flag(image_bytes: bytes, text: str) -> bytes:
    """
    TEMP debug overlay so we can visually confirm template vs flux.
    Draws a tiny semi-transparent label in the top-left corner.
    """
    t = (text or "").strip().upper()
    if not t:
        return image_bytes
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    try:
        font = ImageFont.truetype(FONT_PATH, 14)
    except Exception:
        font = ImageFont.load_default()
    pad = 8
    bbox = draw.textbbox((0, 0), t, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.rounded_rectangle(
        (pad - 4, pad - 3, pad + tw + 6, pad + th + 5),
        radius=6,
        fill=(0, 0, 0, 110),
        outline=(255, 255, 255, 60),
        width=1,
    )
    draw.text((pad, pad), t, font=font, fill=(255, 255, 255, 150))
    out = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _normalize_mode(mode: str | None) -> str:
    m = (mode or MemeMode.PERSONAL).strip().lower()
    return m if m in MemeMode.ALL else MemeMode.PERSONAL


async def fetch_template_image(query: str) -> bytes:
    raise RuntimeError("template fetching is handled by Imgflip caption_image now")


_IMGFLIP_MEMES_CACHE: list[tuple[str, str, str, str]] | None = None
_IMGFLIP_MEMES_CACHE_AT: float = 0.0


def _norm_template_name(s: str) -> str:
    t = (s or "").lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    t = re.sub(r"\\s+", " ", t).strip()
    return t


async def _imgflip_get_memes() -> list[tuple[str, str, str, str]]:
    """Return list of (id, name, norm_name, url) from Imgflip get_memes (cached)."""
    global _IMGFLIP_MEMES_CACHE, _IMGFLIP_MEMES_CACHE_AT  # noqa: PLW0603
    now = time.time()
    if _IMGFLIP_MEMES_CACHE and (now - _IMGFLIP_MEMES_CACHE_AT) < 6 * 60 * 60:
        return _IMGFLIP_MEMES_CACHE

    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as http:
        r = await http.get("https://api.imgflip.com/get_memes")
        r.raise_for_status()
        data = r.json()
        if not data.get("success"):
            raise RuntimeError(f"imgflip get_memes failed: {data}")
        memes = (data.get("data") or {}).get("memes") or []
        out: list[tuple[str, str, str, str]] = []
        for m in memes:
            if not isinstance(m, dict):
                continue
            mid = str(m.get("id") or "").strip()
            name = str(m.get("name") or "").strip()
            url = str(m.get("url") or "").strip()
            if not mid or not name:
                continue
            out.append((mid, name, _norm_template_name(name), url))
        _IMGFLIP_MEMES_CACHE = out
        _IMGFLIP_MEMES_CACHE_AT = now
        return out


async def name_to_template(template_name: str) -> tuple[str, str, str] | None:
    """Exact (normalized) match from Imgflip cached list → (id, canonical_name, url)."""
    q = _norm_template_name(template_name)
    if not q:
        return None
    memes = await _imgflip_get_memes()
    for mid, name, norm, url in memes:
        if norm == q:
            return (mid, name, url)
    return None


async def imgflip_get_template_bytes(url: str) -> bytes:
    u = (url or "").strip()
    if not u:
        raise RuntimeError("imgflip template url missing")
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as http:
        r = await http.get(u)
        r.raise_for_status()
        return r.content


def _looks_like_embedded_text(image_bytes: bytes) -> bool:
    """
    Lightweight heuristic to detect embedded caption text in a template.
    We can't OCR here, so we look for high-contrast edge density in the
    typical meme text zones (top/bottom bands).
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("L")
    except Exception:
        return True

    w, h = img.size
    if w < 120 or h < 120:
        return True

    # Examine top/bottom bands where captions usually sit.
    band = max(12, int(h * 0.16))
    top = img.crop((0, 0, w, band))
    bot = img.crop((0, h - band, w, h))

    def edge_score(band_img: Image.Image) -> float:
        # Simple gradient magnitude approximation.
        small = band_img.resize((max(60, w // 8), max(20, band // 8)), Image.Resampling.BILINEAR)
        px = small.load()
        sw, sh = small.size
        edges = 0
        total = max(1, (sw - 1) * (sh - 1))
        for y in range(sh - 1):
            for x in range(sw - 1):
                a = px[x, y]
                dx = abs(a - px[x + 1, y])
                dy = abs(a - px[x, y + 1])
                if (dx + dy) > 55:  # high-contrast edges
                    edges += 1
        return edges / total

    score = max(edge_score(top), edge_score(bot))
    # Tuned to be conservative: only flag when clearly text-like.
    return score > 0.085


def _crop_caption_bands(image_bytes: bytes, frac: float = 0.14) -> bytes:
    """Crop top/bottom bands and re-encode as PNG (keeps center content)."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    pad = int(h * frac)
    pad = max(8, min(pad, h // 3))
    cropped = img.crop((0, pad, w, h - pad))
    buf = io.BytesIO()
    cropped.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


async def imgflip_caption_image(*, template_id: str, top: str, bottom: str) -> bytes:
    user = settings.imgflip_username
    pw = settings.imgflip_password
    if not user or not pw:
        raise RuntimeError("IMGFLIP_USERNAME/IMGFLIP_PASSWORD not set")

    payload = {
        "template_id": template_id,
        "username": user,
        "password": pw,
        "text0": top,
        "text1": bottom,
    }
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as http:
        r = await http.post("https://api.imgflip.com/caption_image", data=payload)
        r.raise_for_status()
        data = r.json()
        if not data.get("success"):
            raise RuntimeError(f"imgflip caption_image failed: {data}")
        url = str((data.get("data") or {}).get("url") or "").strip()
        if not url:
            raise RuntimeError("imgflip caption_image missing url")
        img_r = await http.get(url)
        img_r.raise_for_status()
        return img_r.content


async def _flux_image_bytes(image_idea: str, variety: str) -> bytes:
    """
    Flux call for original images. Kept intentionally under-specified for natural variation.
    """
    client = replicate.Client(api_token=settings.REPLICATE_API_TOKEN)
    prompt = f"""
A casual, unplanned real-life moment.

{image_idea}

Looks like a normal phone photo:
- imperfect framing
- natural lighting
- slightly messy environment

Scene detail:
{variety}

A normal person with a natural expression.

This should feel like a random real photo, not AI generated.

No text or overlays.
""".strip()

    negative = (
        "text, words, letters, watermark, logo, caption, subtitle, UI, readable screen, "
        "ai art, ai generated, cgi, 3d render, illustration, cartoon, anime, "
        "plastic skin, overly smooth skin, hdr, oversaturated, stock photo, "
        "professional studio, perfect symmetry, glamour lighting, uncanny, extra fingers, "
        "cinematic, studio lighting, perfect face, symmetrical face, hyper realistic, "
        "unreal engine, polished, aesthetic photo, professional photography, sharp focus"
    )

    def _run_flux() -> str:
        out = client.run(
            "black-forest-labs/flux-schnell",
            input={
                "prompt": prompt,
                "aspect_ratio": "1:1",
                "num_outputs": 1,
                "guidance_scale": 3.75,
                "negative_prompt": negative,
            },
        )
        first = out[0]
        if isinstance(first, str):
            return first
        try:
            return str(first)
        except Exception:
            return first  # type: ignore[return-value]

    image_url = await asyncio.to_thread(_run_flux)
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as http:
        resp = await http.get(image_url)
        resp.raise_for_status()
        return resp.content


async def run_meme_generation(
    user_prompt: str,
    plan: dict[str, Any],
    tpl: dict[str, Any],  # noqa: ARG001 — kept for worker/job contract; engine selects template.
    *,
    mode: str | None = None,
    caption_enabled: bool = True,
) -> tuple[bytes, dict[str, Any]]:
    m = _normalize_mode(mode)
    engine_meta = await run_meme_engine(user_prompt, m)

    scenario = engine_meta["scenario"]
    captions = engine_meta["captions"]
    top_text = captions["top_text"]
    bottom_text = captions["bottom_text"]
    score = engine_meta.get("score")
    structure = engine_meta.get("structure")

    # Light mode-aware visual nudges (still mostly uncontrolled, but avoids mode leakage).
    if m == MemeMode.ROAST:
        variety_pool = [
            "awkward tilted framing like a rushed snap",
            "harsh overhead indoor lighting in a cramped space",
            "messy room, realistic background clutter",
            "caught mid-gesture, slightly unflattering angle",
        ]
    elif m == MemeMode.DECISION:
        variety_pool = [
            "faint phone screen glow on the face or hands",
            "low light with visible grain and noise",
            "half-lit room at night, indecisive pause",
            "cluttered desk with late-night energy drink vibe",
        ]
    else:
        variety_pool = [
            "messy room, realistic background clutter",
            "soft indoor lighting, ordinary everyday moment",
            "awkward tilted framing like a rushed snap",
            "background clutter that feels lived-in",
        ]
    variety = random.choice(variety_pool)

    meme_type = str(engine_meta.get("meme_type") or "original").strip().lower()
    template_name = engine_meta.get("template_name")
    template_name_norm = (
        str(template_name).strip() if isinstance(template_name, str) and template_name.strip() else None
    )
    image_search_query = str(engine_meta.get("image_search_query") or "").strip()
    image_idea = str(engine_meta.get("image_idea") or "").strip() or scenario or "person reacting in a messy room"

    raw_image_bytes: bytes
    used_template = False
    template_fetch_err: str | None = None

    matched_name_for_meta: str | None = None
    if meme_type == "template" and template_name_norm:
        match = await name_to_template(template_name_norm)
        if not match:
            print("TEMPLATE MATCH FAILED:", template_name_norm, flush=True)
            raw_image_bytes = await _flux_image_bytes(image_idea, variety)
            used_template = False
            template_fetch_err = "template_match_failed"
        else:
            template_id, matched_name, template_url = match
            matched_name_for_meta = matched_name
            print("TEMPLATE ATTEMPT:", matched_name, f"imgflip:{template_id}", flush=True)
            try:
                if caption_enabled:
                    raw_image_bytes = await imgflip_caption_image(
                        template_id=template_id,
                        top=top_text,
                        bottom=bottom_text,
                    )
                else:
                    # Return the raw template image bytes (no added captions).
                    raw_image_bytes = await imgflip_get_template_bytes(template_url)
                    # Safety: if template likely has embedded text, try a safe crop once; else fallback to Flux.
                    if _looks_like_embedded_text(raw_image_bytes):
                        try:
                            cropped = _crop_caption_bands(raw_image_bytes)
                            if not _looks_like_embedded_text(cropped):
                                raw_image_bytes = cropped
                            else:
                                raise RuntimeError("template contains embedded text")
                        except Exception as e:
                            raise RuntimeError(f"template_not_clean: {e}") from e
                print("TEMPLATE SUCCESS", flush=True)
                used_template = True
                template_fetch_err = None
                image_search_query = matched_name
            except Exception as e:
                print("TEMPLATE FAILED:", str(e), flush=True)
                raw_image_bytes = await _flux_image_bytes(image_idea, variety)
                used_template = False
                template_fetch_err = f"imgflip_failed: {e}"
    else:
        raw_image_bytes = await _flux_image_bytes(image_idea, variety)

    image_source = "template" if used_template else "flux"
    if caption_enabled:
        final_image = raw_image_bytes if used_template else render_meme(raw_image_bytes, top_text, bottom_text)
        final_image = add_source_flag(final_image, "TEMPLATE" if used_template else "FLUX")
    else:
        # No caption overlays, no debug/source watermark.
        final_image = raw_image_bytes
    img = Image.open(io.BytesIO(final_image)).convert("RGB")
    img = img.resize(
        (settings.meme_output_width, settings.meme_output_height),
        Image.Resampling.LANCZOS,
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    resized = buf.getvalue()

    metadata: dict[str, Any] = {
        "captions": captions,
        "template": {
            "name": matched_name_for_meta or tpl["name"],
            "path": "" if matched_name_for_meta else tpl.get("path", ""),
        },
        "score": score,
        "structure": structure,
        "user_prompt": user_prompt,
        "caption_enabled": bool(caption_enabled),
        "reasoning": {
            "scenario": scenario,
            "emotion": "neutral",
            "mode": m,
            "meme_type": meme_type,
            "template_name": template_name_norm,
            "used_template": used_template,
            "image_source": image_source,
            "image_search_query": image_search_query,
            "image_idea": image_idea,
            "template_fetch_error": template_fetch_err,
        },
    }
    return resized, metadata
