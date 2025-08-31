from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Protocol
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
    """采集器基础异常类"""

    pass


class QuotaExceededException(CollectorError):
    """API 配额超限异常

    当采集器检测到 API 配额已用完时抛出此异常。
    调度器捕获此异常后会:
    1. 不更新执行状态记录 (保持上次成功执行的时间戳)
    2. 重新调度到 24 小时后执行

    Attributes:
        api_type: API 类型 (如 'google', 'twitter' 等)
        reset_time: 配额重置时间 (Unix 时间戳)，可选
        message: 异常消息
    """

    def __init__(
        self, api_type: str, reset_time: float | None = None, message: str | None = None
    ):
        self.api_type = api_type
        self.reset_time = reset_time
        if message is None:
            message = f"{api_type} API quota exceeded"
        super().__init__(message)


class BaseCollector(ABC):
    """采集器抽象基类.

    约定: fetch 产生 RawEvent 流; 无需关心去重/持久化, 由 Pipeline 处理.

    支持两种类型的采集器：
    1. 简单采集器：不实现 list_param_jobs() 方法，适用于固定间隔抓取固定内容的场景
    2. 参数化采集器：实现 list_param_jobs() 方法，适用于需要根据不同参数执行不同抓取任务的场景
    """

    name: str  # 唯一名称, 例如 "weibo.home"

    @property
    @abstractmethod
    def default_interval_seconds(self) -> int | None:
        """获取默认执行间隔（秒）

        对于简单采集器，返回固定的间隔时间
        对于参数化采集器，返回默认间隔时间（当参数任务未指定间隔时使用）
        """
        raise NotImplementedError

    def list_param_jobs(self) -> list[tuple[str, int]] | None:
        """列出所有参数化任务配置（可选方法）

        如果采集器需要参数化执行，则重写此方法

        Returns:
            list[tuple[str, int]] | None: 参数任务列表，每个元组包含 (参数, 间隔秒数)
                                        如果返回 None，表示这是一个简单采集器
        """
        return None

    async def setup(self) -> None:  # 可选初始化
        return None

    @abstractmethod
    async def fetch(
        self, param: Any | None = None
    ) -> AsyncIterator[RawEvent]:  # noqa: D401
        """执行抓取并异步生成 RawEvent.

        对于简单采集器，param 应为 None 或被忽略
        对于参数化采集器，param 为具体的抓取参数

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
