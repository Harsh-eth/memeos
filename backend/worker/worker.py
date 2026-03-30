from __future__ import annotations

import asyncio
import base64
import logging
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import torch
from config import settings
from fastapi import HTTPException
from services.generation_pipeline import run_meme_generation
from services.redis_client import (
    close_redis,
    delete_inflight_if_present,
    get_redis,
    init_redis,
    pop_job,
    store_result,
)


def _ensure_templates() -> None:
    idx = settings.templates_dir / "index.json"
    drake = settings.templates_dir / "images" / "drake.png"
    if idx.exists() and drake.exists():
        return
    script = BACKEND_ROOT / "scripts" / "seed_templates.py"
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    if r.returncode != 0:
        logging.error("seed_templates failed: %s", r.stderr or r.stdout)


async def _process_job(
    request_id: str,
    prompt: str,
    plan: dict,
    template: dict,
    device: torch.device,
    inflight_key: str | None,
    mode: str | None,
) -> None:
    redis = await get_redis()
    try:
        try:
            png, meta = await run_meme_generation(
                prompt, plan, template, device=device, mode=mode
            )
            b64 = base64.b64encode(png).decode("ascii")
            await store_result(redis, request_id, image_b64=b64, meta=meta)
        except HTTPException as e:
            d = e.detail
            msg = d if isinstance(d, str) else str(d)
            await store_result(redis, request_id, error=msg, meta={})
        except Exception as e:
            await store_result(redis, request_id, error=str(e), meta={})
    finally:
        await delete_inflight_if_present(redis, inflight_key)


async def _run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not torch.cuda.is_available():
        raise RuntimeError("GPU required but not available")
    device = torch.device("cuda")
    _ensure_templates()
    await init_redis(settings.redis_url)
    redis = await get_redis()
    logging.info("meme worker up device=%s", device)
    while True:
        try:
            job = await pop_job(redis, timeout=5)
            if job is None:
                continue
            rid = str(job["request_id"])
            prompt = str(job["prompt"])
            plan = job["plan"]
            template = job["template"]
            ifk = job.get("inflight_key")
            inflight_key = str(ifk) if ifk else None
            mode = job.get("mode")
            mode_s = str(mode).strip().lower() if mode else None
            await _process_job(rid, prompt, plan, template, device, inflight_key, mode_s)
        except asyncio.CancelledError:
            break
        except Exception:
            logging.exception("worker iteration failed")
            await asyncio.sleep(1)
    await close_redis()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
