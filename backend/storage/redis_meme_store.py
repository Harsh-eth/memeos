from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import redis.asyncio as aioredis

from backend.config import settings


FEED_LIST_KEY = "memeos:feed"
TOP_ZSET_KEY = "memeos:top"
ITEM_KEY_PREFIX = "memeos:item:"
HISTORY_LIST_PREFIX = "memeos:history:"
TOTAL_GENERATED_KEY = "memeos:stats:total_generated"

FEED_MAX = 200
HISTORY_MAX = 50
TOP_MAX = 20


def _item_key(meme_id: str) -> str:
    return f"{ITEM_KEY_PREFIX}{meme_id}"


def _history_key(user_key: str) -> str:
    return f"{HISTORY_LIST_PREFIX}{user_key}"


def public_memes_dir() -> Path:
    d = settings.backend_dir / "data" / "public_memes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def meme_image_path(meme_id: str) -> Path:
    return public_memes_dir() / f"{meme_id}.png"


def meme_image_url(meme_id: str) -> str:
    return f"/meme/{meme_id}.png"


async def store_meme(
    redis: aioredis.Redis,
    *,
    meme_id: str,
    user_key: str,
    image_bytes: bytes,
    metadata: dict[str, Any],
    source: str = "user",
) -> dict[str, Any]:
    ts = int(time.time())

    img_path = meme_image_path(meme_id)
    img_path.write_bytes(image_bytes)

    caps = metadata.get("captions") if isinstance(metadata.get("captions"), dict) else {}
    mode = str((metadata.get("reasoning") or {}).get("mode") or metadata.get("mode") or "").strip().lower()
    score = int(metadata.get("score") or 0)

    item: dict[str, Any] = {
        "id": meme_id,
        "created_at": ts,
        "source": source,
        "image_url": meme_image_url(meme_id),
        "captions": {
            "top_text": str(caps.get("top_text", "")).strip(),
            "bottom_text": str(caps.get("bottom_text", "")).strip(),
        },
        "mode": mode,
        "score": score,
        "metadata": metadata,
    }

    await redis.set(_item_key(meme_id), json.dumps(item, default=str))

    # feed (latest first)
    await redis.lpush(FEED_LIST_KEY, meme_id)
    await redis.ltrim(FEED_LIST_KEY, 0, FEED_MAX - 1)

    # history (latest first)
    await redis.lpush(_history_key(user_key), meme_id)
    await redis.ltrim(_history_key(user_key), 0, HISTORY_MAX - 1)

    # top (score desc, recency tie-break)
    rank_score = float(score) + (ts / 1_000_000_0000.0)
    await redis.zadd(TOP_ZSET_KEY, {meme_id: rank_score})
    n = int(await redis.zcard(TOP_ZSET_KEY))
    if n > TOP_MAX:
        await redis.zremrangebyrank(TOP_ZSET_KEY, 0, n - TOP_MAX - 1)

    await redis.incr(TOTAL_GENERATED_KEY)

    return item


async def get_total_generated(redis: aioredis.Redis) -> int:
    raw = await redis.get(TOTAL_GENERATED_KEY)
    if raw is None:
        return 0
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


async def _fetch_items(redis: aioredis.Redis, ids: list[str]) -> list[dict[str, Any]]:
    if not ids:
        return []
    keys = [_item_key(i) for i in ids]
    raw = await redis.mget(keys)
    out: list[dict[str, Any]] = []
    for s in raw:
        if not s:
            continue
        try:
            out.append(json.loads(s))
        except Exception:
            continue
    return out


async def get_feed(redis: aioredis.Redis, *, limit: int = 40, offset: int = 0) -> list[dict[str, Any]]:
    ids = await redis.lrange(FEED_LIST_KEY, offset, offset + limit - 1)
    return await _fetch_items(redis, [str(x) for x in ids])


async def get_top(redis: aioredis.Redis, *, limit: int = 20) -> list[dict[str, Any]]:
    ids = await redis.zrevrange(TOP_ZSET_KEY, 0, max(0, limit - 1))
    return await _fetch_items(redis, [str(x) for x in ids])


async def get_history(
    redis: aioredis.Redis, *, user_key: str, limit: int = 50, offset: int = 0
) -> list[dict[str, Any]]:
    ids = await redis.lrange(_history_key(user_key), offset, offset + limit - 1)
    return await _fetch_items(redis, [str(x) for x in ids])

