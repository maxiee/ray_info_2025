"""TaskConsumerRegistry: 任务消费者注册表"""

from __future__ import annotations

from typing import Dict, Optional

from .consumer import BaseTaskConsumer


class TaskConsumerRegistry:
    """任务消费者注册表 - 全局单例

    供开发者注册 TaskConsumer，提供统一的查找和管理接口。

    Attributes:
        sources: Key 为 TaskConsumer 的 name，value 为 TaskConsumer 的实例
    """

    def __init__(self):
        """初始化注册表"""
        self.sources: Dict[str, BaseTaskConsumer] = {}

    def register(self, source: BaseTaskConsumer) -> None:
        """注册 TaskConsumer

        Args:
            source: 要注册的 TaskConsumer 实例

        Raises:
            ValueError: 当名称已存在时抛出异常
        """
        if source.name in self.sources:
            raise ValueError(
                f"TaskConsumer with name '{source.name}' already registered"
            )

        self.sources[source.name] = source

    def find(self, name: str) -> Optional[BaseTaskConsumer]:
        """根据名称寻找对应的 TaskConsumer 实例

        Args:
            name: TaskConsumer 的名称

        Returns:
            找到的 TaskConsumer 实例，如果不存在则返回 None
        """
        return self.sources.get(name)

    def unregister(self, name: str) -> bool:
        """注销 TaskConsumer

        Args:
            name: 要注销的 TaskConsumer 名称

        Returns:
            如果成功注销返回 True，如果名称不存在返回 False
        """
        if name in self.sources:
            del self.sources[name]
            return True
        return False

    def list_all(self) -> Dict[str, BaseTaskConsumer]:
        """获取所有已注册的 TaskConsumer

        Returns:
            所有已注册的 TaskConsumer 字典副本
        """
        return self.sources.copy()

    def clear(self) -> None:
        """清空所有注册的 TaskConsumer"""
        self.sources.clear()

    def __len__(self) -> int:
        """返回已注册的 TaskConsumer 数量"""
        return len(self.sources)

    def __contains__(self, name: str) -> bool:
        """检查是否包含指定名称的 TaskConsumer"""
        return name in self.sources


# 全局单例实例
registry = TaskConsumerRegistry()
