from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
import subprocess
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

from backend.agents.feed_agent import FeedAgent
from backend.agents.mode import MemeMode
from backend.agents.planner import PlannerAgent
from backend.agents.template_agent import TemplateAgent
from backend.config import settings
from backend.security.burst_limit import BurstLimiter
from backend.security.daily_limit import DailyIPLimiter
from backend.security.generate_gate import enforce_generate_restrictions, get_client_ip
from backend.security.global_daily_cap import GlobalDailyCap
from backend.security.replay_guard import ReplayGuard
from backend.security.signature import verify_signature
from backend.services.cache import ImageCache
from backend.services.redis_client import (
    close_redis,
    get_redis,
    get_result,
    inflight_key_for,
    init_redis,
    job_queue_length,
    push_user_job,
    try_claim_inflight,
    wait_result_ready,
    redis_client,
)
from backend.storage.feed_store import FeedStore
from backend.storage.redis_meme_store import get_feed as redis_get_feed
from backend.storage.redis_meme_store import get_history as redis_get_history
from backend.storage.redis_meme_store import get_top as redis_get_top
from backend.storage.redis_meme_store import meme_image_path
from backend.storage.redis_meme_store import get_total_generated as redis_get_total_generated
from backend.storage.redis_meme_store import store_meme as redis_store_meme
from backend.trending import get_trending
from backend.utils.content_filter import assert_prompt_allowed
from backend.utils.prompt_validator import validate_and_normalize_prompt

log = logging.getLogger("memeos.generate")


def _log_event(
    request_id: str,
    ip: str,
    prompt_snip: str,
    client_ts: int,
    status: str,
    latency_ms: float,
    cached: bool,
    extra: dict | None = None,
) -> None:
    row: dict = {
        "request_id": request_id,
        "ip": ip,
        "prompt": prompt_snip[:200],
        "client_timestamp": client_ts,
        "status": status,
        "latency_ms": round(latency_ms, 2),
        "cached": cached,
    }
    if extra:
        row.update(extra)
    log.info(json.dumps(row, default=str))


def _ensure_templates() -> None:
    idx = settings.templates_dir / "index.json"
    drake = settings.templates_dir / "images" / "drake.png"
    if idx.exists() and drake.exists():
        return
    script = Path(__file__).resolve().parent / "scripts" / "seed_templates.py"
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    if r.returncode != 0:
        print("seed_templates failed:", r.stderr or r.stdout)


feed_store = FeedStore()
planner = PlannerAgent()
template_agent = TemplateAgent()
feed_agent = FeedAgent(feed_store, get_trending)
daily_limiter = DailyIPLimiter(settings.generate_max_per_ip_per_day)
global_cap = GlobalDailyCap(settings.max_daily_generations_global)
burst = BurstLimiter(settings.burst_interval_seconds)
image_cache = ImageCache(settings.image_cache_path)
replay_guard = ReplayGuard()


async def _resolve_plan_and_template(user_prompt: str) -> tuple[dict, dict]:
    plan = await planner.plan(user_prompt)
    tpl = template_agent.select_record_for_plan(plan)
    return plan, tpl


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    _ensure_templates()
    template_agent._load()  # noqa: SLF001
    await init_redis(settings.redis_url)
    if not settings.memeos_client_token:
        logging.warning("MEMEOS_CLIENT_TOKEN empty — generate may return 503")
    if not settings.memeos_hmac_secret:
        logging.warning("MEMEOS_HMAC_SECRET empty — generate returns 503 until set")
    print(
        f"limits: global_day={settings.max_daily_generations_global} "
        f"per_ip_day={settings.generate_max_per_ip_per_day} burst={settings.burst_interval_seconds}s "
        f"redis={settings.redis_url}"
    )
    yield
    await close_redis()


app = FastAPI(title="MemeOS API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-RateLimit-Remaining",
        "X-RateLimit-Limit",
        "Retry-After",
        "X-Request-Id",
    ],
)


class GenerateBody(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    timestamp: int | None = None
    signature: str | None = None
    mode: str = Field(default=MemeMode.PERSONAL, max_length=32)
    caption_enabled: bool = True

    @field_validator("timestamp")
    @classmethod
    def _ts(cls, v: object) -> int | None:
        if v is None:
            return None
        return int(v)

    @field_validator("mode", mode="before")
    @classmethod
    def _mode_norm(cls, v: object) -> str:
        if v is None or (isinstance(v, str) and not str(v).strip()):
            return MemeMode.PERSONAL
        s = str(v).strip().lower()
        return s if s in MemeMode.ALL else MemeMode.PERSONAL


class AutoToggleBody(BaseModel):
    enabled: bool


def require_generate_headers(request: Request) -> None:
    enforce_generate_restrictions(request)


def _cache_hit_metadata(prompt: str, plan: dict, tpl: dict, mode: str, caption_enabled: bool) -> dict:
    return {
        "plan": plan,
        "captions": {"top_text": "", "bottom_text": ""},
        "template": {"name": tpl["name"], "path": tpl.get("path", "")},
        "user_prompt": prompt,
        "mode": mode,
        "caption_enabled": caption_enabled,
        "reasoning": {
            "tone": plan.get("tone"),
            "chosen_template": tpl["name"],
            "plan": plan,
            "mode": mode,
        },
    }


def _generate_response_headers(remaining_ip: int, request_id: str) -> dict[str, str]:
    return {
        "X-Request-Id": request_id,
        "X-RateLimit-Limit": str(settings.generate_max_per_ip_per_day),
        "X-RateLimit-Remaining": str(remaining_ip),
    }


def _json_generate_ok(
    *,
    request_id: str,
    item_id: str,
    image_b64: str,
    mime: str,
    metadata: dict,
    remaining_ip: int,
    cached: bool,
) -> JSONResponse:
    return JSONResponse(
        content={
            "request_id": request_id,
            "id": item_id,
            "image_base64": image_b64,
            "mime": mime,
            "metadata": metadata,
            "cached": cached,
        },
        headers=_generate_response_headers(remaining_ip, request_id),
    )


def _json_generate_error(
    *,
    request_id: str,
    status_code: int,
    detail: str,
    remaining_ip: int,
    retry_after: str | None = None,
) -> JSONResponse:
    headers = _generate_response_headers(remaining_ip, request_id)
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return JSONResponse(
        status_code=status_code,
        content={
            "request_id": request_id,
            "id": "",
            "cached": False,
            "detail": detail,
        },
        headers=headers,
    )


@app.post("/generate-meme", dependencies=[Depends(require_generate_headers)])
async def generate_meme(request: Request, body: GenerateBody):
    t_req = time.perf_counter()
    request_id = str(uuid.uuid4())
    ip = get_client_ip(request)
    exempt_ip = ip in settings.exempt_ip_set()
    ra_burst = str(max(1, int(math.ceil(settings.burst_interval_seconds))))
    rem_snapshot = (
        daily_limiter.snapshot(ip)[1] if not exempt_ip else settings.generate_max_per_ip_per_day
    )

    def ms() -> float:
        return (time.perf_counter() - t_req) * 1000

    prompt_for_sig = body.prompt.strip()
    if settings.memeos_hmac_secret:
        if body.timestamp is None or body.signature is None:
            return _json_generate_error(
                request_id=request_id,
                status_code=401,
                detail="missing signature",
                remaining_ip=rem_snapshot,
            )
        if not verify_signature(
            prompt_for_sig,
            body.timestamp,
            body.signature,
            settings.memeos_hmac_secret,
            mode=body.mode,
        ):
            _log_event(
                request_id,
                ip,
                prompt_for_sig,
                body.timestamp,
                "fail_validation",
                ms(),
                False,
                {"step": "signature"},
            )
            return _json_generate_error(
                request_id=request_id,
                status_code=401,
                detail="invalid or expired signature",
                remaining_ip=rem_snapshot,
            )

        if not replay_guard.check_and_store(body.signature, body.timestamp):
            _log_event(
                request_id,
                ip,
                prompt_for_sig,
                body.timestamp,
                "fail_replay",
                ms(),
                False,
            )
            return _json_generate_error(
                request_id=request_id,
                status_code=401,
                detail="replay detected",
                remaining_ip=rem_snapshot,
            )

    try:
        prompt_ok = validate_and_normalize_prompt(body.prompt)
        assert_prompt_allowed(prompt_ok)
    except HTTPException as e:
        _log_event(
            request_id,
            ip,
            prompt_for_sig,
            body.timestamp,
            "fail_validation",
            ms(),
            False,
            {"step": "prompt"},
        )
        return _json_generate_error(
            request_id=request_id,
            status_code=int(e.status_code),
            detail=str(e.detail) if e.detail is not None else "validation failed",
            remaining_ip=rem_snapshot,
        )

    try:
        plan, tpl = await _resolve_plan_and_template(prompt_ok)
    except HTTPException as e:
        _log_event(
            request_id,
            ip,
            prompt_ok,
            body.timestamp,
            "fail_validation",
            ms(),
            False,
            {"step": "plan"},
        )
        return _json_generate_error(
            request_id=request_id,
            status_code=int(e.status_code),
            detail=str(e.detail) if e.detail is not None else "plan failed",
            remaining_ip=rem_snapshot,
        )
    except FileNotFoundError as e:
        _log_event(
            request_id,
            ip,
            prompt_ok,
            body.timestamp,
            "fail_validation",
            ms(),
            False,
            {"step": "template_catalog"},
        )
        return _json_generate_error(
            request_id=request_id,
            status_code=500,
            detail=str(e),
            remaining_ip=rem_snapshot,
        )

    tone = str(plan.get("tone") or "")
    tpl_name = str(tpl.get("name") or "")
    ow, oh = settings.meme_output_width, settings.meme_output_height
    mode_norm = body.mode
    caption_enabled = bool(getattr(body, "caption_enabled", True))

    cached_png = image_cache.get(prompt_ok, tone, tpl_name, ow, oh, mode_norm, caption_enabled)
    if cached_png is not None:
        meta = _cache_hit_metadata(prompt_ok, plan, tpl, mode_norm, caption_enabled)
        item = feed_store.add(cached_png, meta, source="user")
        try:
            await redis_store_meme(
                redis_client,
                meme_id=request_id,
                user_key=ip,
                image_bytes=cached_png,
                metadata=meta,
                source="user",
            )
        except Exception:
            log.exception("failed to persist cached meme to redis store")
        if not exempt_ip:
            _, rem = daily_limiter.snapshot(ip)
        else:
            rem = settings.generate_max_per_ip_per_day
        _log_event(
            request_id,
            ip,
            prompt_ok,
            body.timestamp,
            "success_cache",
            ms(),
            True,
            {"feed_id": item["id"]},
        )
        return _json_generate_ok(
            request_id=request_id,
            item_id=item["id"],
            image_b64=item["image_base64"],
            mime="image/png",
            metadata=meta,
            remaining_ip=rem,
            cached=True,
        )

    if not burst.allow(ip):
        _log_event(
            request_id,
            ip,
            prompt_ok,
            body.timestamp,
            "fail_burst",
            ms(),
            False,
        )
        return _json_generate_error(
            request_id=request_id,
            status_code=429,
            detail="too many requests: wait before generating again",
            remaining_ip=rem_snapshot,
            retry_after=ra_burst,
        )

    slots_reserved = False

    def _release_generation_slots() -> None:
        nonlocal slots_reserved
        if not slots_reserved:
            return
        slots_reserved = False
        global_cap.release()
        if not exempt_ip:
            daily_limiter.release(ip)

    try:
        if not global_cap.acquire():
            _log_event(
                request_id,
                ip,
                prompt_ok,
                body.timestamp,
                "fail_validation",
                ms(),
                False,
                {"step": "global_cap"},
            )
            return _json_generate_error(
                request_id=request_id,
                status_code=503,
                detail="service at daily generation capacity",
                remaining_ip=rem_snapshot,
                retry_after="86400",
            )

        if not exempt_ip:
            ok_ip, _ = daily_limiter.acquire(ip)
            if not ok_ip:
                global_cap.release()
                _log_event(
                    request_id,
                    ip,
                    prompt_ok,
                    body.timestamp,
                    "fail_validation",
                    ms(),
                    False,
                    {"step": "ip_daily"},
                )
                return _json_generate_error(
                    request_id=request_id,
                    status_code=429,
                    detail="daily generate limit reached for this network address",
                    remaining_ip=daily_limiter.snapshot(ip)[1],
                    retry_after="86400",
                )

        slots_reserved = True

        redis = await get_redis()
        inflight_k = inflight_key_for(prompt_ok, tone, tpl_name, ow, oh, mode_norm, caption_enabled)
        raw_leader = await redis.get(inflight_k)
        if raw_leader:
            wait_rid = raw_leader.strip()
            is_follower = True
        else:
            claimed = await try_claim_inflight(redis, inflight_k, request_id)
            if claimed:
                wait_rid = request_id
                is_follower = False
            else:
                raw_leader = await redis.get(inflight_k)
                if raw_leader:
                    wait_rid = raw_leader.strip()
                    is_follower = True
                else:
                    claimed2 = await try_claim_inflight(redis, inflight_k, request_id)
                    if claimed2:
                        wait_rid = request_id
                        is_follower = False
                    else:
                        raw_leader = await redis.get(inflight_k)
                        if not raw_leader:
                            _release_generation_slots()
                            rem_busy = (
                                daily_limiter.snapshot(ip)[1]
                                if not exempt_ip
                                else settings.generate_max_per_ip_per_day
                            )
                            return _json_generate_error(
                                request_id=request_id,
                                status_code=503,
                                detail="server busy",
                                remaining_ip=rem_busy,
                            )
                        wait_rid = raw_leader.strip()
                        is_follower = True

        if not is_follower:
            qlen = await job_queue_length(redis)
            if qlen > settings.meme_jobs_max_queued:
                await redis.delete(inflight_k)
                _release_generation_slots()
                rem_busy = (
                    daily_limiter.snapshot(ip)[1]
                    if not exempt_ip
                    else settings.generate_max_per_ip_per_day
                )
                return _json_generate_error(
                    request_id=request_id,
                    status_code=503,
                    detail="server busy",
                    remaining_ip=rem_busy,
                )
            job = {
                "request_id": request_id,
                "prompt": prompt_ok,
                "plan": plan,
                "template": tpl,
                "inflight_key": inflight_k,
                "mode": mode_norm,
                "caption_enabled": caption_enabled,
            }
            await push_user_job(redis, job)

        result = await get_result(redis, wait_rid)
        if result is None:
            try:
                await asyncio.wait_for(
                    wait_result_ready(redis, wait_rid),
                    timeout=settings.generate_timeout_seconds,
                )
            except asyncio.TimeoutError:
                _release_generation_slots()
                _log_event(
                    request_id,
                    ip,
                    prompt_ok,
                    body.timestamp,
                    "fail_timeout",
                    ms(),
                    False,
                )
                rem_err = daily_limiter.snapshot(ip)[1] if not exempt_ip else settings.generate_max_per_ip_per_day
                return _json_generate_error(
                    request_id=request_id,
                    status_code=504,
                    detail="generation timed out",
                    remaining_ip=rem_err,
                    retry_after="10",
                )
            result = await get_result(redis, wait_rid)
        if result is None:
            _release_generation_slots()
            _log_event(
                request_id,
                ip,
                prompt_ok,
                body.timestamp,
                "fail_validation",
                ms(),
                False,
                {"step": "worker", "detail": "missing result after notify"},
            )
            rem_err = daily_limiter.snapshot(ip)[1] if not exempt_ip else settings.generate_max_per_ip_per_day
            return _json_generate_error(
                request_id=request_id,
                status_code=500,
                detail="invalid worker result",
                remaining_ip=rem_err,
            )

        err_msg = result.get("error")
        if err_msg is not None:
            _release_generation_slots()
            _log_event(
                request_id,
                ip,
                prompt_ok,
                body.timestamp,
                "fail_validation",
                ms(),
                False,
                {"step": "worker", "detail": str(err_msg)},
            )
            rem_err = daily_limiter.snapshot(ip)[1] if not exempt_ip else settings.generate_max_per_ip_per_day
            return _json_generate_error(
                request_id=request_id,
                status_code=500,
                detail=str(err_msg),
                remaining_ip=rem_err,
            )

        img_b64 = result.get("image")
        if not img_b64:
            _release_generation_slots()
            _log_event(
                request_id,
                ip,
                prompt_ok,
                body.timestamp,
                "fail_validation",
                ms(),
                False,
                {"step": "worker", "detail": "missing image in result"},
            )
            rem_err = daily_limiter.snapshot(ip)[1] if not exempt_ip else settings.generate_max_per_ip_per_day
            return _json_generate_error(
                request_id=request_id,
                status_code=500,
                detail="invalid worker result",
                remaining_ip=rem_err,
            )

        metadata = result.get("meta") or {}
        try:
            image_bytes = base64.b64decode(img_b64)
        except Exception:
            _release_generation_slots()
            raise

        slots_reserved = False
    except Exception:
        _release_generation_slots()
        raise

    image_cache.put(prompt_ok, tone, tpl_name, ow, oh, image_bytes, mode_norm, caption_enabled)
    item = feed_store.add(image_bytes, metadata, source="user")
    try:
        await redis_store_meme(
            redis,
            meme_id=request_id,
            user_key=ip,
            image_bytes=image_bytes,
            metadata=metadata,
            source="user",
        )
    except Exception:
        # Never fail /generate-meme because feed persistence failed.
        log.exception("failed to persist meme to redis store")
    if not exempt_ip:
        _, rem = daily_limiter.snapshot(ip)
    else:
        rem = settings.generate_max_per_ip_per_day

    _log_event(
        request_id,
        ip,
        prompt_ok,
        body.timestamp,
        "success_generate",
        ms(),
        False,
        {"feed_id": item["id"]},
    )

    return _json_generate_ok(
        request_id=request_id,
        item_id=item["id"],
        image_b64=item["image_base64"],
        mime="image/png",
        metadata=metadata,
        remaining_ip=rem,
        cached=False,
    )


@app.get("/stats")
async def stats():
    """Public aggregate counters (e.g. landing page)."""
    redis = await get_redis()
    total = await redis_get_total_generated(redis)
    return {"total_memes_generated": total}


@app.get("/feed")
async def feed(limit: int = 40, offset: int = 0):
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be 1..100")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")
    redis = await get_redis()
    return {"items": await redis_get_feed(redis, limit=limit, offset=offset)}


@app.get("/top")
async def top(limit: int = 20):
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="limit must be 1..50")
    redis = await get_redis()
    return {"items": await redis_get_top(redis, limit=limit)}


@app.get("/history")
async def history(request: Request, limit: int = 50, offset: int = 0, user_id: str | None = None):
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be 1..100")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")
    ip = get_client_ip(request)
    user_key = (user_id or ip).strip()
    redis = await get_redis()
    return {"items": await redis_get_history(redis, user_key=user_key, limit=limit, offset=offset)}


@app.get("/meme/{meme_id}.png")
async def meme_png(meme_id: str):
    path = meme_image_path(meme_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(path, media_type="image/png")


@app.post("/auto-toggle")
async def auto_toggle(body: AutoToggleBody):
    feed_agent.set_enabled(body.enabled)
    return {"enabled": feed_agent.enabled, "interval_seconds": settings.auto_interval_seconds}


@app.get("/auto-status")
async def auto_status():
    return {"enabled": feed_agent.enabled, "interval_seconds": settings.auto_interval_seconds}


@app.get("/trending")
async def trending():
    return {"topics": get_trending()}


@app.get("/health")
async def health():
    try:
        await redis_client.ping()
        return {"ok": True}
    except Exception:
        return {"ok": False}
