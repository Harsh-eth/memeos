import asyncio
import random
from typing import Any, Awaitable, Callable

from agents.caption import CaptionAgent
from agents.planner import PlannerAgent
from agents.renderer import RendererAgent
from agents.template_agent import TemplateAgent
from config import settings
from storage.feed_store import FeedStore

TrendingProvider = Callable[[], list[str]]


class FeedAgent:
    def __init__(
        self,
        feed_store: FeedStore,
        trending_fn: TrendingProvider,
    ) -> None:
        self._store = feed_store
        self._trending_fn = trending_fn
        self._planner = PlannerAgent()
        self._caption = CaptionAgent()
        self._templates = TemplateAgent()
        self._renderer = RendererAgent()
        self._task: asyncio.Task[None] | None = None
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, on: bool) -> None:
        self._enabled = on
        if on and (self._task is None or self._task.done()):
            self._task = asyncio.create_task(self._loop())
        elif not on and self._task and not self._task.done():
            self._task.cancel()

    async def _loop(self) -> None:
        while self._enabled:
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception:
                pass
            await asyncio.sleep(max(10, settings.auto_interval_seconds))

    async def _tick(self) -> None:
        topics = self._trending_fn()
        if not topics:
            return
        prompt = random.choice(topics)
        plan = await self._planner.plan(f"Auto meme about trending: {prompt}")
        caps = await self._caption.captions(plan, prompt)
        template = self._templates.select_record_for_plan(plan)
        image = self._renderer.render(template, caps["top_text"], caps["bottom_text"])
        meta = {
            "plan": plan,
            "captions": caps,
            "template": {"name": template["name"], "path": template.get("path")},
            "user_prompt": prompt,
            "reasoning": {
                "tone": plan.get("tone"),
                "template": template["name"],
                "plan": plan,
            },
        }
        self._store.add(image, meta, source="auto")
