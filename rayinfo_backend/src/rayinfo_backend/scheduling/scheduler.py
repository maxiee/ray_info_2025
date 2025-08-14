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

        async def job_wrapper():  # APScheduler (AsyncIOScheduler) 可直接调度协程函数
            await self.run_collector_once(collector)

        self.scheduler.add_job(
            job_wrapper,  # 直接传入协程函数; AsyncIOScheduler 会在其事件循环中 create_task
            IntervalTrigger(seconds=interval),
            id=job_id,
            replace_existing=True,
        )
        logger.info("job added: %s interval=%ss", job_id, interval)

    def load_all_collectors(self):
        for col in registry.all():
            self.add_collector_job(col)
