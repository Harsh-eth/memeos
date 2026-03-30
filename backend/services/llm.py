import json
from typing import Any

from openai import OpenAI

from config import settings


async def chat_json(system: str, user: str) -> dict[str, Any]:
    """Call OpenAI for a JSON object; falls back to heuristic parse on failure."""
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=settings.openai_temperature_json,
        response_format={"type": "json_object"},
    )
    text = resp.choices[0].message.content or "{}"
    return json.loads(text)


async def chat_text(system: str, user: str) -> str:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=settings.openai_temperature_text,
    )
    return (resp.choices[0].message.content or "").strip()
