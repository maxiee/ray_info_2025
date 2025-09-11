"""BaseTaskConsumer: 任务生产者/消费者基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from .task import Task


class BaseTaskConsumer(ABC):
    """任务生产者/消费者基类

    任务源（TaskConsumer）是任务的源头，负责生成任务和消费任务。
    采用 OOP 继承设计方式，开发者需要基于该类派生出各种任务源。
    每种任务源表示一种特定的任务。

    Attributes:
        name: 唯一标识符
        concurrent_count: 限制任务并发数，默认为1
    """

    def __init__(self, name: str, concurrent_count: int = 1):
        """初始化 TaskConsumer

        Args:
            name: 唯一标识符
            concurrent_count: 并发数限制，默认为1
        """
        self.name = name
        self.concurrent_count = max(1, concurrent_count)  # 确保至少为1

    @abstractmethod
    async def consume(self, task: Task) -> None:
        """消费一个任务，执行对应具体操作

        Args:
            task: 要消费的任务
        """
        raise NotImplementedError

    def __str__(self) -> str:
        """字符串表示"""
        return (
            f"TaskConsumer(name={self.name}, concurrent_count={self.concurrent_count})"
        )

    def __repr__(self) -> str:
        """详细字符串表示"""
        return f"TaskConsumer(name='{self.name}', concurrent_count={self.concurrent_count})"
