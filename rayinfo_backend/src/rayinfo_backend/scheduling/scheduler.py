from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..collectors.base import (
    BaseCollector,
    QuotaExceededException,
    registry,
)
from ..config.settings import get_settings
from ..pipelines import DedupStage, Pipeline, SqlitePersistStage
from ..utils.instance_id import instance_manager
from .state_manager import CollectorStateManager
from .types import JobKind, make_job_id

logger = logging.getLogger("rayinfo.scheduler")


class SchedulerAdapter:
    """调度器适配器，负责管理与调度所有采集任务。

    - 封装 APScheduler（异步）
    - 统一支持普通与参数化采集器
    - 通过 `CollectorStateManager` 支持断点续传与智能初次/补偿执行
    - 采集结果经 `Pipeline` 去重与持久化

    Attributes:
        scheduler: APScheduler 异步调度器实例
        pipeline: 数据处理管道（去重 + SQLite 持久化）
        state_manager: 采集器状态管理（最后执行时间、次数等）
    """

    def __init__(self):
        """初始化调度器适配器。

        创建异步调度器实例和数据处理管道，管道包含去重阶段和 SQLite 持久化阶段。
        数据库路径从配置文件中读取。同时初始化策略注册器、任务工厂和状态管理器。
        """
        # 负责定时触发任务（异步版，能直接跑协程），自动闹钟面板
        # 设置合理的默认 job 配置，避免误触发堆积
        self.scheduler = AsyncIOScheduler(
            job_defaults={
                "coalesce": True,  # 多个待执行实例合并
                "max_instances": 1,  # 同一任务最多并发1
                "misfire_grace_time": 300,  # 允许最多5分钟的错过执行宽限
            }
        )

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

        # 注意：历史上的策略模式与任务工厂已删除，统一改为状态感知调度

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

    async def run_collector_once(self, collector: BaseCollector) -> None:
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
    ) -> None:
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
            # 防御式：避免出现负延迟
            if retry_delay < 0:
                retry_delay = 0

            # 创建延迟重试任务
            retry_time = time.time() + retry_delay
            # 使用稳定的重试任务 ID，确保仅存在一个挂起的重试任务（若再次触发会替换）
            retry_job_id = make_job_id(collector.name, param, JobKind.QuotaRetry)

            self.scheduler.add_job(
                self.run_collector_with_state_update,
                trigger=DateTrigger(
                    run_date=datetime.fromtimestamp(
                        retry_time, tz=self.scheduler.timezone or timezone.utc
                    )
                ),
                args=[collector, param],
                id=retry_job_id,
                replace_existing=True,
                # max_instances/coalesce 由 job_defaults 统一控制
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
            # 检查是否为参数化采集器（有 list_param_jobs 方法且返回非空值）
            param_jobs = getattr(collector, "list_param_jobs", lambda: None)()
            if param_jobs is not None:
                # 参数化采集器：为每个参数创建独立的状态感知调度
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
                        initial_job_id = make_job_id(
                            collector.name, param_key, JobKind.Initial
                        )
                        self.scheduler.add_job(
                            self.run_collector_with_state_update,
                            trigger=DateTrigger(
                                run_date=datetime.fromtimestamp(
                                    next_run_time,
                                    tz=self.scheduler.timezone or timezone.utc,
                                )
                            ),
                            args=[collector, param_key],
                            id=initial_job_id,
                            replace_existing=True,
                            # 统一由 job_defaults 控制并发/合并
                        )
                        job_ids.append(initial_job_id)

                        logger.info(
                            "添加参数化采集器初始任务 collector=%s param=%s delay=%.1f",
                            collector.name,
                            param_key,
                            next_run_time - time.time(),
                        )

                    # 添加周期性任务
                    periodic_job_id = make_job_id(
                        collector.name, param_key, JobKind.Periodic
                    )
                    self.scheduler.add_job(
                        self.run_collector_with_state_update,
                        trigger=IntervalTrigger(seconds=interval),
                        args=[collector, param_key],
                        id=periodic_job_id,
                        replace_existing=True,
                        # 统一由 job_defaults 控制并发/合并
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
                    initial_job_id = make_job_id(collector.name, None, JobKind.Initial)
                    self.scheduler.add_job(
                        self.run_collector_with_state_update,
                        trigger=DateTrigger(
                            run_date=datetime.fromtimestamp(
                                next_run_time,
                                tz=self.scheduler.timezone or timezone.utc,
                            )
                        ),
                        args=[collector],
                        id=initial_job_id,
                        replace_existing=True,
                        # 统一由 job_defaults 控制并发/合并
                    )
                    job_ids.append(initial_job_id)

                    logger.info(
                        "添加普通采集器初始任务 collector=%s delay=%.1f",
                        collector.name,
                        next_run_time - time.time(),
                    )

                # 添加周期性任务
                periodic_job_id = make_job_id(collector.name, None, JobKind.Periodic)
                self.scheduler.add_job(
                    self.run_collector_with_state_update,
                    trigger=IntervalTrigger(seconds=interval),
                    args=[collector],
                    id=periodic_job_id,
                    replace_existing=True,
                    # 统一由 job_defaults 控制并发/合并
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
