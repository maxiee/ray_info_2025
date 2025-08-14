from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator
from dataclasses import dataclass, field
import time


@dataclass(slots=True)
class RawEvent:
    source: str
    raw: dict
    fetched_at: float = field(default_factory=time.time)


class CollectorError(Exception):
    pass


class BaseCollector(ABC):
    """Collector 抽象基类.

    约定: fetch 产生 RawEvent 流; 无需关心去重/持久化, 由 Pipeline 处理.
    """

    name: str  # 唯一名称, 例如 "weibo.home"
    supports_parameters: bool = False
    default_interval_seconds: int | None = None

    async def setup(self) -> None:  # 可选初始化
        return None

    @abstractmethod
    async def fetch(
        self, param: Any | None = None
    ) -> AsyncIterator[RawEvent]:  # noqa: D401
        """执行抓取并异步生成 RawEvent.

        实现类需实现为 async generator:

        async def fetch(...):
            yield RawEvent(...)
        """
        if False:  # pragma: no cover - 仅用于保持生成器语义
            yield RawEvent(source="_", raw={})  # type: ignore
        raise NotImplementedError

    async def shutdown(self) -> None:  # 可选清理
        return None


class CollectorRegistry:
    """注册中心: 管理所有 Collector 实例 (单例风格)."""

    def __init__(self):
        self._collectors: dict[str, BaseCollector] = {}

    def register(self, collector: BaseCollector):
        if collector.name in self._collectors:
            raise ValueError(f"collector already registered: {collector.name}")
        self._collectors[collector.name] = collector

    def get(self, name: str) -> BaseCollector:
        return self._collectors[name]

    def all(self) -> list[BaseCollector]:
        return list(self._collectors.values())


registry = CollectorRegistry()
