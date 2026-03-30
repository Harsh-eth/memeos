"""
Generate example template PNGs + index.json. Run from repo:
  cd memeos/backend && python scripts/seed_templates.py
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    img_dir = root / "templates" / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    # Drake-style: two horizontal bands, text on the right
    drake = Image.new("RGB", (720, 800), (32, 32, 38))
    d = ImageDraw.Draw(drake)
    d.rectangle((0, 0, 360, 400), fill=(180, 120, 140))
    d.rectangle((0, 400, 360, 800), fill=(90, 140, 110))
    d.rectangle((360, 0, 720, 400), fill=(245, 245, 250))
    d.rectangle((360, 400, 720, 800), fill=(235, 240, 235))
    drake_path = img_dir / "drake.png"
    drake.save(drake_path)

    # Classic: single image, top + bottom safe zones
    classic = Image.new("RGB", (800, 600), (45, 55, 72))
    d2 = ImageDraw.Draw(classic)
    d2.rectangle((40, 80, 760, 420), fill=(70, 85, 110))
    classic_path = img_dir / "classic.png"
    classic.save(classic_path)

    # Two panel: before / after
    twop = Image.new("RGB", (800, 520), (28, 28, 34))
    d3 = ImageDraw.Draw(twop)
    d3.rectangle((0, 0, 800, 260), fill=(60, 60, 70))
    d3.rectangle((0, 260, 800, 520), fill=(50, 70, 55))
    twop_path = img_dir / "two_panel.png"
    twop.save(twop_path)

    catalog = {
        "templates": [
            {
                "name": "drake",
                "path": "images/drake.png",
                "uppercase": True,
                "text_regions": [
                    {"x": 0.52, "y": 0.06, "w": 0.44, "h": 0.38},
                    {"x": 0.52, "y": 0.54, "w": 0.44, "h": 0.38},
                ],
            },
            {
                "name": "classic",
                "path": "images/classic.png",
                "uppercase": True,
                "text_regions": [
                    {"x": 0.05, "y": 0.02, "w": 0.9, "h": 0.2},
                    {"x": 0.05, "y": 0.78, "w": 0.9, "h": 0.2},
                ],
            },
            {
                "name": "two_panel",
                "path": "images/two_panel.png",
                "uppercase": True,
                "text_regions": [
                    {"x": 0.08, "y": 0.08, "w": 0.84, "h": 0.32},
                    {"x": 0.08, "y": 0.58, "w": 0.84, "h": 0.32},
                ],
            },
        ]
    }

    (root / "templates" / "index.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print("Wrote templates to", img_dir)


if __name__ == "__main__":
    main()
