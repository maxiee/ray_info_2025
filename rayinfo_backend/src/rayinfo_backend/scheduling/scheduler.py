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
        """调度普通或参数化 Collector.

        参数化：Collector.supports_parameters 为 True 且实现 list_param_jobs() -> list[(param, interval_seconds)]
        则为每个参数生成 job_id = f"{collector.name}:{param}"。param 内若含空格或特殊字符，对日志影响有限，保持原样。
        若未实现 list_param_jobs 则回退单任务。
        """
        if getattr(collector, "supports_parameters", False) and hasattr(
            collector, "list_param_jobs"
        ):
            try:
                param_jobs = collector.list_param_jobs()  # type: ignore[attr-defined]
            except Exception as e:  # pragma: no cover
                logger.error(
                    "list_param_jobs failed collector=%s error=%s", collector.name, e
                )
                param_jobs = []
            if param_jobs:
                for param, interval in param_jobs:
                    interval = interval or (collector.default_interval_seconds or 60)
                    job_id = f"{collector.name}:{param}"

                    async def param_job_wrapper(p=param, col=collector):
                        # 在执行时传入参数 p
                        logger.debug(
                            "running parameterized job collector=%s param=%s",
                            col.name,
                            p,
                        )
                        events = []
                        agen = col.fetch(param=p)  # type: ignore
                        async for ev in agen:
                            events.append(ev)
                        if events:
                            self.pipeline.run(events)

                    self.scheduler.add_job(
                        param_job_wrapper,
                        IntervalTrigger(seconds=interval),
                        id=job_id,
                        replace_existing=True,
                    )
                    logger.info(
                        "job added (param): %s param=%s interval=%ss",
                        job_id,
                        param,
                        interval,
                    )
                return
        # 非参数化路径
        interval = collector.default_interval_seconds or 60
        job_id = collector.name

        async def job_wrapper():
            await self.run_collector_once(collector)

        self.scheduler.add_job(
            job_wrapper,
            IntervalTrigger(seconds=interval),
            id=job_id,
            replace_existing=True,
        )
        logger.info("job added: %s interval=%ss", job_id, interval)

    def load_all_collectors(self):
        for col in registry.all():
            self.add_collector_job(col)
