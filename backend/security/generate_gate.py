from __future__ import annotations

from urllib.parse import urlparse

from fastapi import HTTPException, Request

from backend.config import settings

HEADER_TOKEN = "x-memeos-client-token"
HEADER_INTENT = "x-memeos-intent"
INTENT_VALUE = "generate"

_CLI_UA_SNIPPETS = (
    "curl/",
    "wget/",
    "python-requests",
    "aiohttp",
    "httpx",
    "go-http-client",
    "java/",
    "libwww",
    "postman",
    "insomnia",
    "httpie",
    "axios/",
)

_ALLOWED_ORIGINS: tuple[str, ...] = (
    "https://memeos.pics",
    "https://www.memeos.pics",
    "https://memeos-eta.vercel.app",
    # dev
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def get_client_ip(request: Request) -> str:
    if settings.trust_proxy_for_ip:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            part = xff.split(",")[0].strip()
            if part:
                return part
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _origin_matches_allowlist(origin_or_referer: str) -> bool:
    raw = origin_or_referer.strip()
    if not raw:
        return False
    try:
        p = urlparse(raw)
        host = p.netloc or p.path.split("/")[0]
        if not host:
            return False
        scheme_host = f"{p.scheme}://{host}" if p.scheme else None
    except Exception:
        return False
    allowed = settings.cors_list()
    for o in allowed:
        ao = urlparse(o)
        ahost = ao.netloc
        if host == ahost or raw.startswith(o.rstrip("/")):
            return True
        if scheme_host and o.rstrip("/") == scheme_host.rstrip("/"):
            return True
    return False


def _check_sec_fetch_site(request: Request) -> None:
    if not settings.require_sec_fetch_site_browser:
        return
    sfs = (request.headers.get("sec-fetch-site") or "").lower()
    if sfs not in ("same-origin", "same-site"):
        raise HTTPException(
            status_code=403,
            detail="forbidden: sec-fetch-site",
        )


def _check_user_agent(request: Request) -> None:
    ua = request.headers.get("user-agent") or ""
    if settings.block_empty_user_agent and len(ua.strip()) < settings.min_user_agent_length:
        raise HTTPException(status_code=403, detail="forbidden: user-agent")
    # TEMP: disable strict CLI blocking for now.
    # (Keep only the empty-UA check above.)


def _check_content_type(request: Request) -> None:
    if not settings.require_json_content_type:
        return
    ct = (request.headers.get("content-type") or "").lower()
    if "application/json" not in ct:
        raise HTTPException(
            status_code=415,
            detail="unsupported media type: application/json required",
        )


def _check_client_token(request: Request) -> None:
    if not settings.memeos_client_token:
        return
    tok = request.headers.get(HEADER_TOKEN)
    # TEMP debug: don't hard-fail when client token is missing/mismatched.
    # This prevents production 403s while we tune CORS + signature UX.
    if not tok:
        return
    if tok != settings.memeos_client_token:
        return


def _check_intent_header(request: Request) -> None:
    intent = (request.headers.get(HEADER_INTENT) or "").strip().lower()
    if intent != INTENT_VALUE:
        raise HTTPException(status_code=403, detail="forbidden: intent header")


def _check_origin_referer(request: Request) -> None:
    if not settings.require_origin_or_referer:
        return
    origin = request.headers.get("origin") or ""
    referer = request.headers.get("referer") or ""
    if not origin and not referer:
        raise HTTPException(status_code=403, detail="forbidden: origin or referer required")
    if origin and not any(origin.startswith(o) for o in _ALLOWED_ORIGINS):
        raise HTTPException(status_code=403, detail="forbidden: origin")
    if referer and not origin:
        if not any(referer.startswith(o) for o in _ALLOWED_ORIGINS):
            raise HTTPException(status_code=403, detail="forbidden: referer")


def enforce_generate_restrictions(request: Request) -> None:
    """
    All generate-only checks: headers, browser hints, content-type.
    Call from a dependency before body is trusted.
    """
    if request.method != "POST":
        return
    # Dev mode: if MEMEOS_CLIENT_TOKEN is unset, skip generate-only header gating.
    if not settings.memeos_client_token:
        return
    _check_content_type(request)
    _check_client_token(request)
    _check_intent_header(request)
    _check_user_agent(request)
    _check_sec_fetch_site(request)
    _check_origin_referer(request)
