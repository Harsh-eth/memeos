import textwrap
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from config import settings


def _find_bold_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        str(Path.home() / "Library/Fonts/Arial Bold.ttf"),
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit_font(draw: ImageDraw.ImageDraw, text: str, box_w: int, box_h: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for size in range(52, 14, -2):
        font = _find_bold_font(size)
        lines = _wrap_lines(draw, text, font, box_w)
        _, th = _text_block_size(draw, lines, font)
        if th <= box_h and lines:
            return font
    return _find_bold_font(18)


def _wrap_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    words = text.replace("\n", " ").split()
    if not words:
        return [""]
    lines: list[str] = []
    current: list[str] = []
    for w in words:
        trial = (" ".join(current + [w])).strip()
        bbox = draw.textbbox((0, 0), trial, font=font, stroke_width=2)
        if bbox[2] - bbox[0] <= max_width or not current:
            current.append(w)
        else:
            lines.append(" ".join(current))
            current = [w]
    if current:
        lines.append(" ".join(current))
    return lines


def _text_block_size(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> tuple[int, int]:
    w = 0
    h = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=2)
        lw = bbox[2] - bbox[0]
        lh = bbox[3] - bbox[1]
        w = max(w, lw)
        h += lh + 4
    return w, h


class RendererAgent:
    def render(
        self,
        template: dict[str, Any],
        top_text: str,
        bottom_text: str,
    ) -> bytes:
        path = template.get("abs_path") or str(settings.templates_dir / template["path"])
        img = Image.open(path).convert("RGBA")
        W, H = img.size
        draw = ImageDraw.Draw(img)

        regions = template.get("text_regions") or []
        texts = [top_text, bottom_text]
        for i, region in enumerate(regions):
            if i >= len(texts):
                break
            t = texts[i].upper() if template.get("uppercase", True) else texts[i]
            self._draw_region(draw, W, H, region, t)

        buf = BytesIO()
        img.convert("RGB").save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    def _draw_region(
        self,
        draw: ImageDraw.ImageDraw,
        W: int,
        H: int,
        region: dict[str, Any],
        text: str,
    ) -> None:
        x0 = int(region["x"] * W)
        y0 = int(region["y"] * H)
        x1 = int((region["x"] + region["w"]) * W)
        y1 = int((region["y"] + region["h"]) * H)
        box_w = max(20, x1 - x0)
        box_h = max(20, y1 - y0)
        font = _fit_font(draw, text, box_w - 8, box_h - 8)
        lines = _wrap_lines(draw, text, font, box_w - 8)
        tw, th = _text_block_size(draw, lines, font)
        cx = (x0 + x1) // 2
        start_y = y0 + max(4, (box_h - th) // 2)

        y = start_y
        fill = (255, 255, 255, 255)
        stroke = (0, 0, 0, 255)
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font, stroke_width=3)
            lw = bbox[2] - bbox[0]
            x = cx - lw // 2
            draw.text((x, y), line, font=font, fill=fill, stroke_width=3, stroke_fill=stroke)
            y += (bbox[3] - bbox[1]) + 4
