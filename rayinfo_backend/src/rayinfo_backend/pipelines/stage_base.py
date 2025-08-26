"""管道处理阶段抽象基类模块

本模块包含所有管道阶段的抽象基类和通用功能。
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict

from ..collectors.base import RawEvent


class PipelineStage(ABC):
    """管道处理阶段抽象基类

    提供统一的错误处理、指标收集和生命周期管理。
    所有管道阶段都应继承此类并实现具体的处理逻辑。
    """

    def __init__(self, stage_name: str | None = None):
        """初始化管道阶段

        Args:
            stage_name: 阶段名称，用于日志和指标标识
        """
        self.stage_name = stage_name or self.__class__.__name__
        self.logger = logging.getLogger(f"rayinfo.pipeline.{self.stage_name.lower()}")

        # 指标统计
        self._metrics = {
            "processed_count": 0,
            "error_count": 0,
            "total_processing_time": 0.0,
            "last_processed_at": None,
            "last_error_at": None,
        }

    @abstractmethod
    def _process_impl(self, events: list[RawEvent]) -> list[RawEvent]:
        """实际的处理逻辑实现

        子类必须实现此方法来定义具体的处理逻辑。

        Args:
            events: 要处理的事件列表

        Returns:
            处理后的事件列表
        """
        raise NotImplementedError

    def process(self, events: list[RawEvent]) -> list[RawEvent]:
        """处理事件列表的统一入口

        提供统一的错误处理、指标收集和日志记录。

        Args:
            events: 要处理的事件列表

        Returns:
            处理后的事件列表
        """
        if not events:
            return events

        start_time = time.time()

        try:
            self.logger.debug(f"开始处理 {len(events)} 个事件")

            # 调用子类实现
            result = self._process_impl(events)

            # 更新指标
            processing_time = time.time() - start_time
            self._metrics["processed_count"] += len(events)
            self._metrics["total_processing_time"] += processing_time
            self._metrics["last_processed_at"] = datetime.utcnow()

            self.logger.debug(
                f"处理完成，输入 {len(events)} 个，输出 {len(result)} 个，耗时 {processing_time:.3f}s"
            )

            return result

        except Exception as e:
            processing_time = time.time() - start_time
            self._metrics["error_count"] += 1
            self._metrics["last_error_at"] = datetime.utcnow()

            self.logger.error(
                f"处理阶段失败: {e}，处理事件数: {len(events)}，耗时: {processing_time:.3f}s"
            )

            # 尝试错误恢复
            return self.handle_error(e, events)

    def handle_error(self, error: Exception, events: list[RawEvent]) -> list[RawEvent]:
        """错误处理机制

        子类可以重写此方法来实现自定义的错误处理逻辑。
        默认实现返回空列表，防止错误传播。

        Args:
            error: 发生的异常
            events: 导致错误的事件列表

        Returns:
            错误恢复后的事件列表（默认为空）
        """
        self.logger.warning(f"使用默认错误处理，丢弃 {len(events)} 个事件")
        return []

    def get_metrics(self) -> Dict[str, Any]:
        """获取处理指标

        Returns:
            包含各种指标的字典
        """
        metrics = self._metrics.copy()
        metrics["stage_name"] = self.stage_name

        # 计算平均处理时间
        if metrics["processed_count"] > 0:
            metrics["avg_processing_time"] = (
                metrics["total_processing_time"] / metrics["processed_count"]
            )
        else:
            metrics["avg_processing_time"] = 0.0

        return metrics

    def reset_metrics(self):
        """重置指标统计"""
        self._metrics = {
            "processed_count": 0,
            "error_count": 0,
            "total_processing_time": 0.0,
            "last_processed_at": None,
            "last_error_at": None,
        }
