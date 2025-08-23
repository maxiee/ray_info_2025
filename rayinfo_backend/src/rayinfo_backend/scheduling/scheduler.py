from __future__ import annotations

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..collectors.base import registry, BaseCollector, ParameterizedCollector
from ..pipelines.base import Pipeline, DedupStage, SqlitePersistStage
from ..config.settings import get_settings

logger = logging.getLogger("rayinfo.scheduler")


class SchedulerAdapter:
    """调度器适配器，负责管理和调度所有数据收集任务。

    这个类封装了 APScheduler 异步调度器，提供了对数据收集器(Collector)的
    统一调度管理。支持普通收集器和参数化收集器两种模式：
    - 普通收集器：按固定间隔执行单个收集任务
    - 参数化收集器：支持多个参数配置，每个参数对应一个独立的调度任务

    收集到的数据会通过数据处理管道进行去重和持久化处理。

    Attributes:
        scheduler (AsyncIOScheduler): APScheduler 异步调度器，负责定时触发任务
        pipeline (Pipeline): 数据处理管道，包含去重和持久化阶段
    """

    def __init__(self):
        """初始化调度器适配器。

        创建异步调度器实例和数据处理管道，管道包含去重阶段和 SQLite 持久化阶段。
        数据库路径从配置文件中读取。
        """
        # 负责定时触发任务（异步版，能直接跑协程），自动闹钟面板
        self.scheduler = AsyncIOScheduler()
        
        # 从配置中获取存储设置
        settings = get_settings()
        
        # Collector 捞到的数据顺序加工，传送带 - 现在使用真正的 SQLite 存储
        self.pipeline = Pipeline([
            DedupStage(max_size=1000),  # 去重阶段
            SqlitePersistStage(settings.storage.db_path)  # SQLite 持久化阶段
        ])
        
        logger.info(f"调度器初始化完成，数据库路径: {settings.storage.db_path}")

    def start(self):
        """启动调度器。

        开始执行所有已添加的定时任务。
        """
        self.scheduler.start()

    def shutdown(self):
        """关闭调度器。

        停止所有正在运行的任务，不等待任务完成即立即关闭。
        """
        self.scheduler.shutdown(wait=False)

    async def run_collector_once(self, collector: BaseCollector):
        """执行单次数据收集任务。

        调用指定收集器抓取数据，将获取的所有事件聚合成列表后
        交给数据处理管道进行后续处理。

        Args:
            collector (BaseCollector): 要执行的数据收集器实例
        """
        logger.info("[run] collector=%s", collector.name)
        events = []
        # 返回异步生成器；可以“边等网络边产出”而不是一次性全返回，减小等待时间浪费。
        agen = collector.fetch()
        async for ev in agen:  # type: ignore
            events.append(ev)
        if events:
            self.pipeline.run(events)

    def add_collector_job(self, collector: BaseCollector):
        """添加数据收集器的调度任务。

        根据收集器类型自动选择调度模式：

        1. 参数化收集器模式：
           - 条件：collector 是 ParameterizedCollector 的实例
           - 行为：为每个参数配置创建独立的调度任务
           - 任务ID格式："{collector.name}:{param}"
           - 每个参数任务使用独立的执行间隔

        2. 普通收集器模式：
           - 条件：collector 是 SimpleCollector 的实例
           - 行为：创建单个调度任务
           - 任务ID：collector.name
           - 使用收集器默认间隔或60秒

        Args:
            collector (BaseCollector): 要添加调度的数据收集器实例

        Note:
            - 如果同名任务已存在，会替换现有任务
            - 参数字符串中的空格或特殊字符会保持原样
            - 调度间隔优先使用参数配置，否则使用收集器默认值
        """
        # 检查是否为参数化采集器
        if isinstance(collector, ParameterizedCollector):
            try:
                param_jobs = collector.list_param_jobs()
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

        # 非参数化路径 (包括 SimpleCollector 和其他 BaseCollector 子类)
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
        """加载并添加所有已注册的收集器任务。

        遍历收集器注册表中的所有收集器，为每个收集器添加相应的调度任务。
        这是批量初始化所有数据收集任务的便捷方法。
        """
        for col in registry.all():
            self.add_collector_job(col)
