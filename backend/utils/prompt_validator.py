from __future__ import annotations

import re
from typing import Final

from fastapi import HTTPException

_MIN_LEN: Final[int] = 5
_MAX_LEN: Final[int] = 200
# Same character repeated 7+ times in a row (spam / abuse)
_RE_REPEATED_RUN: Final[re.Pattern[str]] = re.compile(r"(.)\1{6,}")


def validate_and_normalize_prompt(raw: str) -> str:
    """
    Strip whitespace; enforce 5..200 chars; reject 7+ same character in a row.
    Returns normalized prompt for pipeline, cache, and signing (must match client).
    """
    if raw is None:
        raise HTTPException(status_code=400, detail="prompt required")
    text = raw.strip()
    if len(text) < _MIN_LEN:
        raise HTTPException(status_code=400, detail="prompt too short")
    if len(text) > _MAX_LEN:
        raise HTTPException(status_code=400, detail="prompt too long")
    if _RE_REPEATED_RUN.search(text):
        raise HTTPException(status_code=400, detail="prompt contains repeated character spam")
    return text
