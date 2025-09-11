"""CollectorTaskConsumer: 将现有 BaseCollector 适配为 TaskConsumer"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..collectors.base import BaseCollector
from ..pipelines import Pipeline
from .consumer import BaseTaskConsumer
from .task import Task


class CollectorTaskConsumer(BaseTaskConsumer):
    """采集器任务消费者适配器
    
    将现有的 BaseCollector 适配为 TaskConsumer，提供向新调度器的迁移桥梁。
    保持与现有代码的兼容性，同时支持新的调度框架。
    
    Attributes:
        collector: 被适配的采集器实例
        pipeline: 数据处理管道
        param: 参数化采集器的参数（可选）
    """
    
    def __init__(
        self,
        collector: BaseCollector,
        pipeline: Pipeline,
        param: Optional[str] = None,
        concurrent_count: Optional[int] = None,
    ):
        """初始化采集器任务消费者
        
        Args:
            collector: 被适配的采集器实例
            pipeline: 数据处理管道
            param: 参数化采集器的参数
            concurrent_count: 并发数限制，如果为 None 则使用默认值1
        """
        # 构造唯一名称
        name = collector.name
        if param is not None:
            name = f"{collector.name}:{param}"
        
        # 设置并发数
        if concurrent_count is None:
            concurrent_count = 1  # 默认并发数为1，保持安全
        
        super().__init__(name, concurrent_count)
        
        self.collector = collector
        self.pipeline = pipeline
        self.param = param
        self._log = logging.getLogger(f"rayinfo.collector_adapter.{name}")
    
    def produce(self, args: Optional[Dict[str, Any]] = None) -> Task:
        """创建采集任务
        
        Args:
            args: 任务参数，可以包含：
                - schedule_at: 调度时间（可选）
                - 其他自定义参数
                
        Returns:
            创建的 Task 实例
        """
        # 提取调度时间
        schedule_at = None
        task_args = args or {}
        
        if "schedule_at" in task_args:
            schedule_at = task_args.pop("schedule_at")
            if isinstance(schedule_at, str):
                schedule_at = datetime.fromisoformat(schedule_at)
        
        # 添加采集器参数
        if self.param is not None:
            task_args["param"] = self.param
        
        return Task(
            source=self.name,
            args=task_args,
            schedule_at=schedule_at,
        )
    
    async def consume(self, task: Task) -> None:
        """消费采集任务
        
        执行采集器的 fetch 方法，并将结果通过管道处理。
        
        Args:
            task: 要消费的任务
        """
        try:
            self._log.info(
                "[run] 开始执行采集器任务 task=%s",
                task.uuid[:8]
            )
            
            # 提取参数
            param = task.args.get("param")
            
            # 执行采集并处理数据
            event_count = await self.pipeline.run_from_async_generator(
                self.collector.fetch(param=param)
            )
            
            self._log.info(
                "[run] 采集任务完成 task=%s events=%d",
                task.uuid[:8],
                event_count
            )
            
        except Exception as e:
            self._log.exception(
                "[run] 采集器任务执行失败 task=%s error=%s",
                task.uuid[:8],
                e
            )
            raise


def create_collector_consumer(
    collector: BaseCollector,
    pipeline: Pipeline,
    param: Optional[str] = None,
) -> CollectorTaskConsumer:
    """创建采集器任务消费者的便捷函数
    
    Args:
        collector: 采集器实例
        pipeline: 数据处理管道
        param: 参数化采集器的参数
        
    Returns:
        创建的采集器任务消费者
    """
    return CollectorTaskConsumer(
        collector=collector,
        pipeline=pipeline,
        param=param,
    )