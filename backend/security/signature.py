from __future__ import annotations

# NOTE:
# HMAC secret is exposed in frontend (VITE_), so this is NOT secure against
# determined attackers. It only prevents casual abuse.
#
# Signing payload (UTF-8): f"{prompt}\\n{mode}\\n{timestamp}" with mode default "personal".

import hashlib
import hmac
import time
from typing import Final

_MAX_SKEW_SEC: Final[int] = 300


def signing_message(prompt: str, timestamp: int, mode: str = "personal") -> bytes:
    """Canonical payload: prompt, mode, and timestamp as UTF-8 lines (LF-separated)."""
    m = (mode or "personal").strip().lower()
    return f"{prompt}\n{m}\n{int(timestamp)}".encode("utf-8")


def generate_signature(prompt: str, timestamp: int, secret: str, mode: str = "personal") -> str:
    """Return lowercase hex HMAC-SHA256 of signing_message."""
    key = secret.encode("utf-8")
    msg = signing_message(prompt, timestamp, mode)
    digest = hmac.new(key, msg, hashlib.sha256).hexdigest()
    return digest


def verify_signature(
    prompt: str, timestamp: int, signature: str, secret: str, mode: str = "personal"
) -> bool:
    """
    True if signature matches and timestamp is within ±MAX_SKEW_SEC of server time.
    Uses hmac.compare_digest for the MAC; timestamp checked in constant time for bounds only.
    """
    if not secret or not signature:
        return False
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    now = int(time.time())
    if abs(now - ts) > _MAX_SKEW_SEC:
        return False
    try:
        sig_norm = signature.strip().lower()
        if len(sig_norm) != 64 or any(c not in "0123456789abcdef" for c in sig_norm):
            return False
    except Exception:
        return False
    expected = generate_signature(prompt, ts, secret, mode)
    return hmac.compare_digest(expected, sig_norm)
