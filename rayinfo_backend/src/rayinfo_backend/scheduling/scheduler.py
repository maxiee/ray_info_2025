from __future__ import annotations

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..collectors.base import registry, BaseCollector
from ..pipelines.base import Pipeline, DedupStage, PersistStage

logger = logging.getLogger("rayinfo.scheduler")


class SchedulerAdapter:
    def __init__(self):
        # 负责定时触发任务（异步版，能直接跑协程），自动闹钟面板
        self.scheduler = AsyncIOScheduler()
        # Collector 捞到的数据顺序加工，传送带
        self.pipeline = Pipeline([DedupStage(), PersistStage()])

    def start(self):
        self.scheduler.start()

    def shutdown(self):
        self.scheduler.shutdown(wait=False)

    async def run_collector_once(self, collector: BaseCollector):
        """让 Collector 抓取一批，聚合成列表后交给 pipeline."""
        logger.info("[run] collector=%s", collector.name)
        events = []
        # 返回异步生成器；可以“边等网络边产出”而不是一次性全返回，减小等待时间浪费。
        agen = collector.fetch()
        async for ev in agen:  # type: ignore
            events.append(ev)
        if events:
            self.pipeline.run(events)

    def add_collector_job(self, collector: BaseCollector):
        """给闹钟设时间，把“每隔 X 秒执行一次 Collector”写进调度器."""
        interval = collector.default_interval_seconds or 60
        job_id = collector.name

        # APScheduler (AsyncIOScheduler) 可直接调度协程函数
        # 内部 async 闭包，APScheduler 实际调用的协程入口，值班提醒
        async def job_wrapper():
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
