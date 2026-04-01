from __future__ import annotations

import json
from typing import Any

from backend.config import settings

_EMOTION_TO_TEMPLATE: dict[str, str] = {
    "regret": "wojak_cry",
    "denial": "clown",
    "overconfidence": "gigachad",
    "delusion": "clown",
    "frustration": "angry_wojak",
    "cope": "copium",
}

_DEFAULT_TEMPLATE = "clown"


def _load_catalog() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    root = settings.templates_dir
    idx = root / "index.json"
    if not idx.is_file():
        return {}, []
    raw = json.loads(idx.read_text(encoding="utf-8"))
    by_name: dict[str, dict[str, Any]] = {}
    catalog: list[dict[str, Any]] = []
    for item in raw.get("templates", []):
        path = root / item["path"]
        if not path.is_file():
            continue
        entry = {**item, "abs_path": str(path.resolve())}
        catalog.append(entry)
        by_name[item["name"]] = entry
    return by_name, catalog


class TemplateAgent:
    def __init__(self) -> None:
        self._load()

    def _load(self) -> None:
        self._by_name, self._catalog = _load_catalog()

    def select(self, emotion: str) -> str:
        key = (emotion or "").strip().lower()
        return _EMOTION_TO_TEMPLATE.get(key, _DEFAULT_TEMPLATE)

    def select_record_for_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Resolve PNG template dict for planner output (drake / classic / two_panel)."""
        want = str(plan.get("template_type", "classic")).lower()
        preference = {
            "drake": ["drake", "two_panel", "classic"],
            "two_panel": ["two_panel", "drake", "classic"],
            "classic": ["classic", "two_panel", "drake"],
        }.get(want, ["classic", "drake", "two_panel"])
        for name in preference:
            if name in self._by_name:
                return dict(self._by_name[name])
        if self._catalog:
            return dict(self._catalog[0])
        raise FileNotFoundError(
            "No templates loaded. Run: python scripts/seed_templates.py from the backend folder."
        )
