from __future__ import annotations

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..collectors.base import registry, BaseCollector, ParameterizedCollector
from ..pipelines import Pipeline, DedupStage, SqlitePersistStage
from ..config.settings import get_settings
from ..utils.instance_id import instance_manager
from .strategies import (
    create_default_strategy_registry,
    SimpleJobFactory,
    ParameterizedJobFactory,
    StrategyRegistry,
)

logger = logging.getLogger("rayinfo.scheduler")


class SchedulerAdapter:
    """调度器适配器，负责管理和调度所有数据收集任务。

    这个类封装了 APScheduler 异步调度器，使用策略模式提供对数据收集器(Collector)的
    统一调度管理。支持普通收集器和参数化收集器两种模式：
    - 普通收集器：按固定间隔执行单个收集任务
    - 参数化收集器：支持多个参数配置，每个参数对应一个独立的调度任务

    收集到的数据会通过数据处理管道进行去重和持久化处理。
    使用策略模式重构后，简化了原本复杂的条件分支逻辑，提升了代码可读性和可扩展性。

    Attributes:
        scheduler (AsyncIOScheduler): APScheduler 异步调度器，负责定时触发任务
        pipeline (Pipeline): 数据处理管道，包含去重和持久化阶段
        strategy_registry (StrategyRegistry): 策略注册器，管理不同采集器类型的调度策略
        simple_job_factory (SimpleJobFactory): 普通采集器任务工厂
        param_job_factory (ParameterizedJobFactory): 参数化采集器任务工厂
    """

    def __init__(self):
        """初始化调度器适配器。

        创建异步调度器实例和数据处理管道，管道包含去重阶段和 SQLite 持久化阶段。
        数据库路径从配置文件中读取。同时初始化策略注册器和任务工厂。
        """
        # 负责定时触发任务（异步版，能直接跑协程），自动闹钟面板
        self.scheduler = AsyncIOScheduler()

        # 从配置中获取存储设置
        settings = get_settings()

        # Collector 捞到的数据顺序加工，传送带 - 现在使用真正的 SQLite 存储
        self.pipeline = Pipeline(
            [
                DedupStage(max_size=1000),  # 去重阶段
                SqlitePersistStage(settings.storage.db_path),  # SQLite 持久化阶段
            ]
        )

        # 初始化策略模式组件
        self.strategy_registry = create_default_strategy_registry()
        self.simple_job_factory = SimpleJobFactory(self.run_collector_once)

        # 为参数化任务工厂创建适配器函数
        def pipeline_runner(events: list) -> None:
            self.pipeline.run(events)

        self.param_job_factory = ParameterizedJobFactory(pipeline_runner)

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

    def add_collector_job(self, collector: BaseCollector) -> list[str]:
        """添加数据收集器的调度任务。

        使用策略模式根据收集器类型自动选择合适的调度策略：
        - 参数化收集器：为每个参数配置创建独立的调度任务
        - 普通收集器：创建单个调度任务

        Args:
            collector (BaseCollector): 要添加调度的数据收集器实例

        Returns:
            list[str]: 已添加的任务ID列表

        Note:
            - 如果同名任务已存在，会替换现有任务
            - 调度间隔优先使用参数配置，否则使用收集器默认值
            - 通过策略模式简化了原本复杂的条件分支逻辑
        """
        try:
            # 获取对应的调度策略
            strategy = self.strategy_registry.get_strategy(collector)

            # 选择合适的任务工厂
            if isinstance(collector, ParameterizedCollector):
                job_factory = self.param_job_factory
            else:
                job_factory = self.simple_job_factory

            # 使用策略执行调度
            job_ids = strategy.schedule_job(collector, self.scheduler, job_factory)

            logger.info(
                "采集器调度完成 collector=%s 添加任务数=%d",
                collector.name,
                len(job_ids),
            )

            return job_ids

        except Exception as e:
            logger.error("添加采集器任务失败 collector=%s error=%s", collector.name, e)
            return []

    def load_all_collectors(self):
        """加载并添加所有已注册的收集器任务。

        遍历收集器注册表中的所有收集器，为每个收集器添加相应的调度任务。
        这是批量初始化所有数据收集任务的便捷方法。
        """
        for col in registry.all():
            self.add_collector_job(col)

    async def run_instance_by_id(self, instance_id: str) -> dict[str, str]:
        """根据实例ID手动触发采集器实例。

        Args:
            instance_id: 采集器实例的唯一ID

        Returns:
            dict[str, str]: 执行结果，包含状态和消息

        Raises:
            ValueError: 当实例ID不存在时抛出异常
        """
        # 获取实例信息
        instance = instance_manager.get_instance(instance_id)
        if instance is None:
            raise ValueError(f"Instance not found: {instance_id}")

        try:
            if instance.param is None:
                # 普通采集器
                logger.info(
                    "[manual] 手动触发普通采集器实例 collector=%s instance_id=%s",
                    instance.collector.name,
                    instance_id,
                )
                await self.run_collector_once(instance.collector)
            else:
                # 参数化采集器
                logger.info(
                    "[manual] 手动触发参数化采集器实例 collector=%s param=%s instance_id=%s",
                    instance.collector.name,
                    instance.param,
                    instance_id,
                )
                events = []
                agen = instance.collector.fetch(param=instance.param)  # type: ignore
                async for ev in agen:
                    events.append(ev)
                if events:
                    self.pipeline.run(events)

            return {
                "status": "success",
                "message": f"Successfully triggered instance {instance_id}",
            }
        except Exception as e:
            logger.error(
                "[manual] 手动触发实例失败 instance_id=%s error=%s", instance_id, str(e)
            )
            return {
                "status": "error",
                "message": f"Failed to trigger instance {instance_id}: {str(e)}",
            }
