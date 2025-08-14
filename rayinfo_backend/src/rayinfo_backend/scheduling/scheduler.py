from __future__ import annotations

import asyncio
import logging
from typing import Callable
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..collectors.base import registry, BaseCollector
from ..pipelines.base import Pipeline, DedupStage, PersistStage

logger = logging.getLogger("rayinfo.scheduler")


class SchedulerAdapter:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.pipeline = Pipeline([DedupStage(), PersistStage()])

    def start(self):
        self.scheduler.start()

    def shutdown(self):
        self.scheduler.shutdown(wait=False)

    async def run_collector_once(self, collector: BaseCollector):
        logger.info("[run] collector=%s", collector.name)
        events = []
        agen = collector.fetch()
        async for ev in agen:  # type: ignore
            events.append(ev)
        if events:
            self.pipeline.run(events)

    def add_collector_job(self, collector: BaseCollector):
        interval = collector.default_interval_seconds or 60
        job_id = collector.name

        async def job_wrapper():  # 封装为 async job
            await self.run_collector_once(collector)

        # APScheduler 需要调用可调用对象, async 用 asyncio.create_task 包装
        def synced():
            asyncio.create_task(job_wrapper())

        self.scheduler.add_job(
            synced,
            IntervalTrigger(seconds=interval),
            id=job_id,
            replace_existing=True,
        )
        logger.info("job added: %s interval=%ss", job_id, interval)

    def load_all_collectors(self):
        for col in registry.all():
            self.add_collector_job(col)
