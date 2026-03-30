from __future__ import annotations

from fastapi import HTTPException

# Basic blocklist — extend via config if needed
_BLOCKED_SUBSTRINGS = frozenset(
    (
        "nsfw",
        "nude",
        "nudes",
        "porn",
        "xxx",
        "gore",
        "gory",
        "snuff",
        "rape",
        "kill yourself",
        "kys",
        "nazi",
        "hitler",
        "child porn",
        "cp ",
        "loli",
        "terrorist",
        "bomb how to",
        "faggot",
        "retard",
        "tranny",
        "n1gger",
        "nigger",
        "chink",
        "spic",
        "kike",
    )
)


def assert_prompt_allowed(prompt_normalized: str) -> None:
    lower = prompt_normalized.lower()
    for bad in _BLOCKED_SUBSTRINGS:
        if bad in lower:
            raise HTTPException(status_code=400, detail="prompt blocked by content policy")
