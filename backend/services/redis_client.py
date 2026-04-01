from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

import redis.asyncio as aioredis

from config import settings

MEME_JOBS_HIGH = "meme_jobs_high"
MEME_JOBS_LOW = "meme_jobs_low"
RESULT_TTL_SEC = 60
RESULT_READY_PREFIX = "result_ready:"
INFLIGHT_PREFIX = "inflight:"
INFLIGHT_TTL_SEC = 30
RESULT_POLL_INTERVAL_SEC = 0.2

# Single shared Redis client instance (reused everywhere).
redis_client: aioredis.Redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)


def result_key(request_id: str) -> str:
    return f"result:{request_id}"


def result_ready_key(request_id: str) -> str:
    return f"{RESULT_READY_PREFIX}{request_id}"


def inflight_key_for(
    prompt: str,
    tone: str,
    template_name: str,
    width: int,
    height: int,
    mode: str = "personal",
    caption_enabled: bool = True,
) -> str:
    raw = (
        f"{prompt}\x00{tone}\x00{template_name}\x00{int(width)}\x00{int(height)}\x00{mode}\x00"
        f"{'cap1' if caption_enabled else 'cap0'}"
    )
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{INFLIGHT_PREFIX}{h}"


async def try_claim_inflight(
    client: aioredis.Redis, key: str, request_id: str, ex: int = INFLIGHT_TTL_SEC
) -> bool:
    return bool(await client.set(key, request_id, nx=True, ex=ex))


async def init_redis(url: str) -> aioredis.Redis:
    # Enforce single connection source of truth.
    await redis_client.ping()
    return redis_client


async def close_redis() -> None:
    await redis_client.aclose()


async def get_redis() -> aioredis.Redis:
    return redis_client


async def push_user_job(client: aioredis.Redis, job: dict[str, Any]) -> None:
    payload = json.dumps(job, default=str)
    await client.lpush(MEME_JOBS_HIGH, payload)


async def push_feed_job(client: aioredis.Redis, job: dict[str, Any]) -> None:
    payload = json.dumps(job, default=str)
    await client.lpush(MEME_JOBS_LOW, payload)


async def job_queue_length(client: aioredis.Redis) -> int:
    hi = int(await client.llen(MEME_JOBS_HIGH))
    lo = int(await client.llen(MEME_JOBS_LOW))
    return hi + lo


async def wait_result_poll_only(client: aioredis.Redis, request_id: str) -> None:
    """Poll result:{id} until present (safe when multiple waiters share one completion)."""
    while True:
        raw = await client.get(result_key(request_id))
        if raw is not None:
            return
        await asyncio.sleep(RESULT_POLL_INTERVAL_SEC)


async def wait_result_ready(
    client: aioredis.Redis,
    request_id: str,
) -> None:
    """
    Block until the worker signals completion for this request_id.
    Caller should wrap with asyncio.wait_for(..., timeout=...) for API timeouts.
    Uses BLPOP on result_ready:{id} (worker RPUSHes after writing result:{id}).
    """
    key = result_ready_key(request_id)
    out = await client.blpop(key, timeout=0)
    if out is None:
        raise RuntimeError("unexpected: BLPOP returned None with timeout=0")


async def pop_job(client: aioredis.Redis, timeout: int) -> dict[str, Any] | None:
    out = await client.brpop([MEME_JOBS_HIGH, MEME_JOBS_LOW], timeout=timeout)
    if out is None:
        return None
    _, raw = out
    return json.loads(raw)


async def delete_inflight_if_present(
    client: aioredis.Redis, inflight_key: str | None
) -> None:
    if inflight_key:
        await client.delete(inflight_key)


async def store_result(
    client: aioredis.Redis,
    request_id: str,
    *,
    image_b64: str | None = None,
    meta: dict[str, Any] | None = None,
    error: str | None = None,
    ex: int = RESULT_TTL_SEC,
) -> None:
    body: dict[str, Any] = {"meta": meta or {}}
    if error is not None:
        body["error"] = error
    else:
        if image_b64 is None:
            body["error"] = "missing image"
        else:
            body["image"] = image_b64
    rkey = result_key(request_id)
    nkey = result_ready_key(request_id)
    async with client.pipeline(transaction=True) as pipe:
        pipe.set(rkey, json.dumps(body, default=str), ex=ex)
        pipe.rpush(nkey, "1")
        pipe.expire(nkey, ex)
        await pipe.execute()


async def get_result(client: aioredis.Redis, request_id: str) -> dict[str, Any] | None:
    raw = await client.get(result_key(request_id))
    if raw is None:
        return None
    return json.loads(raw)
