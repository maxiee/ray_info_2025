from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from ..collectors.base import (
    registry,
    BaseCollector,
    ParameterizedCollector,
    QuotaExceededException,
)
from ..pipelines import Pipeline, DedupStage, SqlitePersistStage
from ..config.settings import get_settings
from ..utils.instance_id import instance_manager
from .state_manager import CollectorStateManager
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
        数据库路径从配置文件中读取。同时初始化策略注册器、任务工厂和状态管理器。
        """
        # 负责定时触发任务（异步版，能直接跑协程），自动闹钟面板
        # 使用默认设置，但设置misfire_grace_time来避免任务堆积
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

        # 初始化状态管理器（用于断点续传）
        self.state_manager = CollectorStateManager.get_instance(
            settings.storage.db_path
        )

        # 初始化策略模式组件
        self.strategy_registry = create_default_strategy_registry()

        # 为普通采集器创建适配器函数（只接受collector参数）
        async def simple_collector_runner(collector: BaseCollector) -> None:
            await self.run_collector_with_state_update(collector, None)

        self.simple_job_factory = SimpleJobFactory(simple_collector_runner)

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

    async def run_collector_with_state_update(
        self, collector: BaseCollector, param: Optional[str] = None
    ):
        """执行单次数据收集任务并更新状态。

        调用指定收集器抓取数据，将获取的所有事件聚合成列表后
        交给数据处理管道进行后续处理，并更新采集器执行状态。

        Args:
            collector (BaseCollector): 要执行的数据收集器实例
            param (str, optional): 参数化采集器的参数
        """
        start_time = time.time()
        should_update_state = True  # 标记是否应该更新状态

        try:
            logger.info(
                "[run] 开始执行采集器 collector=%s param=%s", collector.name, param
            )

            events = []

            # 执行采集任务
            if param is not None:
                # 参数化采集器
                agen = collector.fetch(param=param)  # type: ignore
            else:
                # 普通采集器
                agen = collector.fetch()

            async for ev in agen:  # type: ignore
                events.append(ev)

            # 处理采集到的数据
            if events:
                self.pipeline.run(events)
                logger.info(
                    "[run] 采集完成 collector=%s param=%s events=%d",
                    collector.name,
                    param,
                    len(events),
                )
            else:
                logger.info(
                    "[run] 采集完成但无数据 collector=%s param=%s",
                    collector.name,
                    param,
                )

        except QuotaExceededException as e:
            # API 配额超限异常的特殊处理
            logger.warning(
                "[run] API配额超限 collector=%s param=%s api_type=%s reset_time=%s - 不更新状态，重调度到24小时后",
                collector.name,
                param,
                e.api_type,
                e.reset_time,
            )

            # 计算重调度时间（24小时后，或根据 reset_time）
            retry_delay = 24 * 3600  # 默认24小时
            if e.reset_time and e.reset_time > time.time():
                # 使用 API 提供的重置时间
                retry_delay = e.reset_time - time.time()
                logger.info(
                    "[run] 使用API提供的重置时间 delay=%.1f小时", retry_delay / 3600
                )

            # 创建延迟重试任务
            retry_time = time.time() + retry_delay
            retry_job_id = f"{collector.name}:{param}:quota_retry:{int(time.time())}"

            self.scheduler.add_job(
                self.run_collector_with_state_update,
                trigger=DateTrigger(run_date=datetime.fromtimestamp(retry_time)),
                args=[collector, param],
                id=retry_job_id,
                replace_existing=True,
                max_instances=1,  # 限制同一个任务最多同时运行1个实例
                coalesce=True,  # 如果有多个待执行实例，合并为一个
            )

            logger.info(
                "[run] 已安排配额重试任务 job_id=%s retry_in=%.1f小时",
                retry_job_id,
                retry_delay / 3600,
            )

            # 标记不更新状态
            should_update_state = False

        except Exception as e:
            logger.error(
                "[run] 采集器执行失败 collector=%s param=%s error=%s",
                collector.name,
                param,
                e,
            )
            raise
        finally:
            # 只有在正常执行或非配额异常时才更新状态
            if should_update_state:
                try:
                    self.state_manager.update_execution_time(
                        collector_name=collector.name,
                        param_key=param,  # 直接传递，状态管理器会处理None
                        timestamp=start_time,
                    )
                except Exception as e:
                    logger.warning(
                        "更新采集器状态失败 collector=%s param=%s error=%s",
                        collector.name,
                        param,
                        e,
                    )
            else:
                logger.info(
                    "[run] 由于配额异常，跳过状态更新 collector=%s param=%s",
                    collector.name,
                    param,
                )

    def add_collector_job_with_state(self, collector: BaseCollector) -> list[str]:
        """添加带状态感知的数据收集器调度任务。

        集成断点续传功能，根据上次执行时间智能决定初始调度策略：
        - 如果首次运行或超过1个间隔时间，立即执行一次
        - 否则根据剩余时间延迟执行

        然后添加正常的周期性调度任务。

        Args:
            collector (BaseCollector): 要添加调度的数据收集器实例

        Returns:
            list[str]: 已添加的任务ID列表
        """
        job_ids = []

        try:
            if isinstance(collector, ParameterizedCollector):
                # 参数化采集器：为每个参数创建独立的状态感知调度
                param_jobs = collector.list_param_jobs()
                for param_key, interval in param_jobs:
                    # 确保 interval 不为 None
                    if interval is None:
                        logger.warning(
                            "参数化采集器任务间隔为空，跳过 collector=%s param=%s",
                            collector.name,
                            param_key,
                        )
                        continue

                    # 注册实例到实例管理器
                    instance_id = instance_manager.register_instance(
                        collector, param_key
                    )
                    logger.debug(
                        "注册参数化采集器实例 collector=%s param=%s instance_id=%s",
                        collector.name,
                        param_key,
                        instance_id,
                    )

                    # 计算初始执行时间
                    next_run_time = self.state_manager.calculate_next_run_time(
                        collector_name=collector.name,
                        param_key=param_key,
                        interval_seconds=interval,
                    )

                    # 添加初始执行任务（一次性）
                    if self.state_manager.should_run_immediately(
                        collector_name=collector.name,
                        param_key=param_key,
                        interval_seconds=interval,
                    ):
                        initial_job_id = f"{collector.name}:{param_key}:initial"
                        self.scheduler.add_job(
                            self.run_collector_with_state_update,
                            trigger=DateTrigger(
                                run_date=datetime.fromtimestamp(next_run_time)
                            ),
                            args=[collector, param_key],
                            id=initial_job_id,
                            replace_existing=True,
                            max_instances=1,  # 限制同一个任务最多同时运行1个实例
                            coalesce=True,  # 如果有多个待执行实例，合并为一个
                        )
                        job_ids.append(initial_job_id)

                        logger.info(
                            "添加参数化采集器初始任务 collector=%s param=%s delay=%.1f",
                            collector.name,
                            param_key,
                            next_run_time - time.time(),
                        )

                    # 添加周期性任务
                    periodic_job_id = f"{collector.name}:{param_key}:periodic"
                    self.scheduler.add_job(
                        self.run_collector_with_state_update,
                        trigger=IntervalTrigger(seconds=interval),
                        args=[collector, param_key],
                        id=periodic_job_id,
                        replace_existing=True,
                        max_instances=1,  # 限制同一个任务最多同时运行1个实例
                        coalesce=True,  # 如果有多个待执行实例，合并为一个
                    )
                    job_ids.append(periodic_job_id)

                    logger.info(
                        "添加参数化采集器周期任务 collector=%s param=%s interval=%d",
                        collector.name,
                        param_key,
                        interval,
                    )
            else:
                # 普通采集器
                interval = collector.default_interval_seconds
                if interval is None:
                    logger.warning(
                        "普通采集器间隔为空，使用默认值60秒 collector=%s",
                        collector.name,
                    )
                    interval = 60

                # 注册实例到实例管理器
                instance_id = instance_manager.register_instance(collector, None)
                logger.debug(
                    "注册普通采集器实例 collector=%s instance_id=%s",
                    collector.name,
                    instance_id,
                )

                # 计算初始执行时间
                next_run_time = self.state_manager.calculate_next_run_time(
                    collector_name=collector.name,
                    param_key=None,
                    interval_seconds=interval,
                )

                # 添加初始执行任务（一次性）
                if self.state_manager.should_run_immediately(
                    collector_name=collector.name,
                    param_key=None,
                    interval_seconds=interval,
                ):
                    initial_job_id = f"{collector.name}:initial"
                    self.scheduler.add_job(
                        self.run_collector_with_state_update,
                        trigger=DateTrigger(
                            run_date=datetime.fromtimestamp(next_run_time)
                        ),
                        args=[collector],
                        id=initial_job_id,
                        replace_existing=True,
                        max_instances=1,  # 限制同一个任务最多同时运行1个实例
                        coalesce=True,  # 如果有多个待执行实例，合并为一个
                    )
                    job_ids.append(initial_job_id)

                    logger.info(
                        "添加普通采集器初始任务 collector=%s delay=%.1f",
                        collector.name,
                        next_run_time - time.time(),
                    )

                # 添加周期性任务
                periodic_job_id = f"{collector.name}:periodic"
                self.scheduler.add_job(
                    self.run_collector_with_state_update,
                    trigger=IntervalTrigger(seconds=interval),
                    args=[collector],
                    id=periodic_job_id,
                    replace_existing=True,
                    max_instances=1,  # 限制同一个任务最多同时运行1个实例
                    coalesce=True,  # 如果有多个待执行实例，合并为一个
                )
                job_ids.append(periodic_job_id)

                logger.info(
                    "添加普通采集器周期任务 collector=%s interval=%d",
                    collector.name,
                    interval,
                )

            logger.info(
                "状态感知调度完成 collector=%s 添加任务数=%d",
                collector.name,
                len(job_ids),
            )

            return job_ids

        except Exception as e:
            logger.error(
                "添加状态感知采集器任务失败 collector=%s error=%s", collector.name, e
            )
            return []

    def add_collector_job(self, collector: BaseCollector) -> list[str]:
        """添加数据收集器的调度任务。

        现在使用状态感知的调度逻辑，支持断点续传功能。
        根据上次执行时间智能决定初始调度策略。

        Args:
            collector (BaseCollector): 要添加调度的数据收集器实例

        Returns:
            list[str]: 已添加的任务ID列表
        """
        return self.add_collector_job_with_state(collector)

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
                await self.run_collector_with_state_update(instance.collector)
            else:
                # 参数化采集器
                logger.info(
                    "[manual] 手动触发参数化采集器实例 collector=%s param=%s instance_id=%s",
                    instance.collector.name,
                    instance.param,
                    instance_id,
                )
                await self.run_collector_with_state_update(
                    instance.collector, instance.param
                )

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

    def load_all_collectors(self):
        """加载并添加所有已注册的收集器任务。

        遍历收集器注册表中的所有收集器，为每个收集器添加相应的状态感知调度任务。
        这是批量初始化所有数据收集任务的便捷方法。
        """
        for col in registry.all():
            self.add_collector_job_with_state(col)
