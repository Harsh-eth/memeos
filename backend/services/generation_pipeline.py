from __future__ import annotations

import io
import json
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from agents.mode import MemeMode
from config import settings
from fastapi import HTTPException
from services.meme_engine import run_meme_engine


def _resize_png_torch(png_bytes: bytes, w: int, h: int, device: torch.device) -> bytes:
    im = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    arr = np.asarray(im, dtype=np.float32) / 255.0
    t = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)
    t = t.to(device)
    t = F.interpolate(t, size=(int(h), int(w)), mode="bilinear", align_corners=False)
    out = (t.squeeze(0).permute(1, 2, 0).clamp(0, 1) * 255).to(torch.uint8).cpu().numpy()
    buf = io.BytesIO()
    Image.fromarray(out, mode="RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _template_path_for_id(template_id: str) -> str:
    root = settings.templates_dir
    idx = root / "index.json"
    if not idx.is_file():
        return ""
    raw = json.loads(idx.read_text(encoding="utf-8"))
    for item in raw.get("templates", []):
        if item.get("name") == template_id:
            return str(item.get("path", ""))
    return ""


def _normalize_mode(mode: str | None) -> str:
    m = (mode or MemeMode.PERSONAL).strip().lower()
    return m if m in MemeMode.ALL else MemeMode.PERSONAL


async def run_meme_generation(
    user_prompt: str,
    plan: dict[str, Any],
    tpl: dict[str, Any],  # noqa: ARG001 — kept for worker/job contract; engine selects template.
    *,
    device: torch.device,
    mode: str | None = None,
) -> tuple[bytes, dict[str, Any]]:
    m = _normalize_mode(mode)
    try:
        image_bytes, engine_meta = await run_meme_engine(user_prompt, m)
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    resized = _resize_png_torch(
        image_bytes, settings.meme_output_width, settings.meme_output_height, device
    )

    template_id = str(engine_meta.get("template", ""))
    score = engine_meta.get("score")
    metadata: dict[str, Any] = {
        "plan": plan,
        "captions": engine_meta.get("captions", {}),
        "template": {"name": template_id, "path": _template_path_for_id(template_id)},
        "user_prompt": user_prompt,
        "mode": m,
        "reasoning": {
            "tone": plan.get("tone"),
            "chosen_template": template_id,
            "plan": plan,
            "scenario": engine_meta.get("scenario", ""),
            "emotion": engine_meta.get("emotion", ""),
            "mode": m,
            "score": score,
        },
    }
    if score is not None:
        metadata["score"] = score
    return resized, metadata
