"""管道主模块

本模块包含主要的Pipeline类，负责管理和执行管道阶段。
"""

from __future__ import annotations
from typing import AsyncIterator

from ..collectors.base import RawEvent
from .stage_base import PipelineStage


class Pipeline:
    """数据处理管道

    管理和执行一系列管道处理阶段，按顺序处理数据。
    """

    def __init__(self, stages: list[PipelineStage]):
        """初始化管道

        Args:
            stages: 管道阶段列表，按顺序执行
        """
        self.stages = stages

    def run(self, events: list[RawEvent]) -> list[RawEvent]:
        """运行管道处理

        Args:
            events: 要处理的事件列表

        Returns:
            处理后的事件列表
        """
        data = events
        for stage in self.stages:
            data = stage.process(data)
        return data

    async def run_from_async_generator(self, async_generator: AsyncIterator[RawEvent]) -> int:
        """从异步生成器运行管道处理

        Args:
            async_generator: 产生RawEvent的异步生成器

        Returns:
            处理的事件数量
        """
        events = []
        async for event in async_generator:
            events.append(event)
        
        # 使用现有的run方法处理事件
        processed_events = self.run(events)
        return len(processed_events)
