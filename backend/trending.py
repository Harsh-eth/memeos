"""Trending topics: Phase 1 static list; Phase 2 can swap in APIs."""

STATIC_TRENDING = [
    "btc dumping",
    "ai agents hype",
    "startup burnout",
    "vibe coding",
    "another L2 launch",
    "touch grass discourse",
    "npm install anxiety",
    "meeting that could be an email",
]


def get_trending() -> list[str]:
    return list(STATIC_TRENDING)
