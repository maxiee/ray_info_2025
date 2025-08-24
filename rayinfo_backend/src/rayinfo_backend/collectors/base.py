from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator
from dataclasses import dataclass, field
import time


@dataclass(slots=True)
class RawEvent:

    # 标记出处，便于后续区分与幂等键组成。源自哪个平台/采集器，如 "weibo.home"
    source: str

    # 保存平台原始/半结构化数据，不做“过早清洗”
    raw: dict

    # 抓取发生的时间（Unix 秒）
    fetched_at: float = field(default_factory=time.time)

    # 调试标记，如果为 True，该事件不会被持久化到数据库
    debug: bool = False


class CollectorError(Exception):
    pass


class BaseCollector(ABC):
    """采集器抽象基类.

    约定: fetch 产生 RawEvent 流; 无需关心去重/持久化, 由 Pipeline 处理.
    所有具体采集器都应继承 SimpleCollector 或 ParameterizedCollector.
    """

    name: str  # 唯一名称, 例如 "weibo.home"
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


class SimpleCollector(BaseCollector):
    """普通采集器基类.

    不支持参数化，每次调用 fetch 时 param 应为 None.
    适用于固定间隔抓取固定内容的场景，如微博首页、特定 RSS 源等.
    """

    @abstractmethod
    async def fetch(
        self, param: Any | None = None
    ) -> AsyncIterator[RawEvent]:  # noqa: D401
        """执行抓取并异步生成 RawEvent.

        Args:
            param: 应始终为 None，如传入非 None 值将被忽略

        Yields:
            RawEvent: 抓取到的原始事件数据
        """
        if False:  # pragma: no cover - 仅用于保持生成器语义
            yield RawEvent(source="_", raw={})  # type: ignore
        raise NotImplementedError


class ParameterizedCollector(BaseCollector):
    """参数化采集器基类.

    支持根据不同参数执行不同的抓取任务.
    适用于搜索引擎查询、用户时间线抓取等需要动态参数的场景.
    """

    @abstractmethod
    def list_param_jobs(self) -> list[tuple[str, int]]:
        """列出所有参数化任务配置.

        Returns:
            list[tuple[str, int]]: 参数任务列表，每个元组包含 (参数, 间隔秒数)
        """
        raise NotImplementedError

    @abstractmethod
    async def fetch(
        self, param: Any | None = None
    ) -> AsyncIterator[RawEvent]:  # noqa: D401
        """根据参数执行抓取并异步生成 RawEvent.

        Args:
            param: 具体的抓取参数，如搜索关键词、用户ID等

        Yields:
            RawEvent: 抓取到的原始事件数据
        """
        if False:  # pragma: no cover - 仅用于保持生成器语义
            yield RawEvent(source="_", raw={})  # type: ignore
        raise NotImplementedError


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
