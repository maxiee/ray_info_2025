"""调度策略模块

实现任务调度的策略模式，将复杂的调度逻辑从 SchedulerAdapter 中分离出来。
通过策略模式简化 add_collector_job 方法，提升代码可读性和可测试性。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Dict, Type, Callable, Any

from apscheduler.triggers.interval import IntervalTrigger

from ..collectors.base import BaseCollector, ParameterizedCollector, SimpleCollector
from ..utils.instance_id import instance_manager

logger = logging.getLogger("rayinfo.scheduler.strategy")


class JobFactory(ABC):
    """任务工厂抽象基类

    负责为不同类型的采集器创建合适的任务函数。
    """

    @abstractmethod
    def create_job(
        self, collector: BaseCollector, param: str | None = None
    ) -> Callable[[], Any]:
        """创建任务函数

        Args:
            collector: 采集器实例
            param: 任务参数，普通采集器为None

        Returns:
            可调用的异步任务函数
        """
        raise NotImplementedError


class SimpleJobFactory(JobFactory):
    """普通采集器任务工厂"""

    def __init__(self, run_collector_func: Callable[[BaseCollector], Any]):
        """初始化普通任务工厂

        Args:
            run_collector_func: 执行单次采集的函数，通常是 SchedulerAdapter.run_collector_once
        """
        self.run_collector_func = run_collector_func

    def create_job(
        self, collector: BaseCollector, param: str | None = None
    ) -> Callable[[], Any]:
        """为普通采集器创建任务函数"""

        async def job_wrapper():
            logger.debug("执行普通采集器任务 collector=%s", collector.name)
            await self.run_collector_func(collector)

        return job_wrapper


class ParameterizedJobFactory(JobFactory):
    """参数化采集器任务工厂"""

    def __init__(self, pipeline_run_func: Callable[[list], None]):
        """初始化参数化任务工厂

        Args:
            pipeline_run_func: 管道处理函数，通常是 Pipeline.run
        """
        self.pipeline_run_func = pipeline_run_func

    def create_job(
        self, collector: BaseCollector, param: str | None = None
    ) -> Callable[[], Any]:
        """为参数化采集器创建任务函数"""
        if param is None:
            raise ValueError("参数化采集器必须提供参数")

        async def param_job_wrapper():
            logger.debug(
                "执行参数化采集器任务 collector=%s param=%s", collector.name, param
            )
            events = []
            agen = collector.fetch(param=param)  # type: ignore
            async for ev in agen:
                events.append(ev)
            if events:
                self.pipeline_run_func(events)

        return param_job_wrapper


class JobScheduleStrategy(ABC):
    """任务调度策略抽象基类

    定义了为采集器添加调度任务的统一接口。
    不同类型的采集器使用不同的策略实现。
    """

    @abstractmethod
    def schedule_job(
        self,
        collector: BaseCollector,
        scheduler: Any,  # APScheduler instance
        job_factory: JobFactory,
    ) -> list[str]:
        """为采集器安排调度任务

        Args:
            collector: 要调度的采集器实例
            scheduler: APScheduler 调度器实例
            job_factory: 任务工厂实例

        Returns:
            已添加的任务ID列表
        """
        raise NotImplementedError


class SimpleJobStrategy(JobScheduleStrategy):
    """普通采集器调度策略

    为普通采集器创建单个调度任务。
    """

    def schedule_job(
        self, collector: BaseCollector, scheduler: Any, job_factory: JobFactory
    ) -> list[str]:
        """为普通采集器创建调度任务"""
        interval = collector.default_interval_seconds or 60
        job_id = collector.name

        # 注册实例ID（普通采集器param为None）
        instance_id = instance_manager.register_instance(collector, None)

        # 创建任务函数
        job_func = job_factory.create_job(collector, None)

        # 添加到调度器
        scheduler.add_job(
            job_func,
            IntervalTrigger(seconds=interval),
            id=job_id,
            replace_existing=True,
            max_instances=1,  # 限制同一个任务最多同时运行1个实例
            coalesce=True,  # 如果有多个待执行实例，合并为一个
        )

        logger.info(
            "普通任务已添加: %s interval=%ss instance_id=%s",
            job_id,
            interval,
            instance_id,
        )

        return [job_id]


class ParameterizedJobStrategy(JobScheduleStrategy):
    """参数化采集器调度策略

    为参数化采集器的每个参数创建独立的调度任务。
    """

    def schedule_job(
        self, collector: BaseCollector, scheduler: Any, job_factory: JobFactory
    ) -> list[str]:
        """为参数化采集器创建多个调度任务"""
        if not isinstance(collector, ParameterizedCollector):
            raise ValueError(f"采集器 {collector.name} 不是参数化采集器")

        try:
            param_jobs = collector.list_param_jobs()
        except Exception as e:
            logger.error(
                "获取参数化任务列表失败 collector=%s error=%s", collector.name, e
            )
            return []

        if not param_jobs:
            logger.warning("参数化采集器 %s 没有配置任何参数任务", collector.name)
            return []

        job_ids = []
        for param, interval in param_jobs:
            interval = interval or (collector.default_interval_seconds or 60)
            job_id = f"{collector.name}:{param}"

            # 注册实例ID
            instance_id = instance_manager.register_instance(collector, param)

            # 创建任务函数
            job_func = job_factory.create_job(collector, param)

            # 添加到调度器
            scheduler.add_job(
                job_func,
                IntervalTrigger(seconds=interval),
                id=job_id,
                replace_existing=True,
                max_instances=1,  # 限制同一个任务最多同时运行1个实例
                coalesce=True,  # 如果有多个待执行实例，合并为一个
            )

            logger.info(
                "参数化任务已添加: %s param=%s interval=%ss instance_id=%s",
                job_id,
                param,
                interval,
                instance_id,
            )

            job_ids.append(job_id)

        return job_ids


class StrategyRegistry:
    """策略注册器

    管理不同采集器类型对应的调度策略。
    """

    def __init__(self):
        self._strategies: Dict[Type[BaseCollector], JobScheduleStrategy] = {}
        self._default_strategy: JobScheduleStrategy | None = None

    def register_strategy(
        self, collector_type: Type[BaseCollector], strategy: JobScheduleStrategy
    ):
        """注册采集器类型对应的策略"""
        self._strategies[collector_type] = strategy

    def set_default_strategy(self, strategy: JobScheduleStrategy):
        """设置默认策略"""
        self._default_strategy = strategy

    def get_strategy(self, collector: BaseCollector) -> JobScheduleStrategy:
        """获取采集器对应的策略

        优先使用Protocol接口检查，提升类型安全性。
        """
        # 直接类型匹配
        collector_type = type(collector)
        if collector_type in self._strategies:
            return self._strategies[collector_type]

        # 基于Protocol接口匹配（更类型安全）
        if hasattr(collector, "list_param_jobs") and callable(
            getattr(collector, "list_param_jobs")
        ):
            # 实现了Parameterizable接口
            for registered_type, strategy in self._strategies.items():
                if registered_type == ParameterizedCollector:
                    return strategy

        # 基于继承关系匹配（后备方案）
        for registered_type, strategy in self._strategies.items():
            if isinstance(collector, registered_type):
                return strategy

        # 返回默认策略
        if self._default_strategy:
            return self._default_strategy

        raise ValueError(f"没有找到采集器 {collector.name} 对应的调度策略")


def create_default_strategy_registry() -> StrategyRegistry:
    """创建默认的策略注册器

    Returns:
        配置好的策略注册器实例
    """
    registry = StrategyRegistry()

    # 注册策略
    registry.register_strategy(ParameterizedCollector, ParameterizedJobStrategy())
    registry.register_strategy(SimpleCollector, SimpleJobStrategy())

    # 设置默认策略（用于其他BaseCollector子类）
    registry.set_default_strategy(SimpleJobStrategy())

    return registry
