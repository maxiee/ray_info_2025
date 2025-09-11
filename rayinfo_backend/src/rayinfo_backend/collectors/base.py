from __future__ import annotations

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


class CollectorRetryableException(CollectorError):
    """采集器可重试异常

    当采集器执行失败但可以通过延迟重试解决时抛出此异常。
    调度器捕获此异常后会:
    1. 不更新执行状态记录 (保持上次成功执行的时间戳)
    2. 延迟重新调度任务

    这个异常适用于各种需要延迟重试的场景，如：
    - API 配额超限
    - 网络临时故障
    - 第三方服务临时不可用
    - 其他临时性错误

    Attributes:
        retry_after: 建议的重试延迟时间（秒），如果为 None 则使用默认值（1小时）
        retry_reason: 重试原因的简短描述
        message: 异常消息
    """

    def __init__(
        self,
        retry_reason: str = "unknown",
        retry_after: float | None = None,
        message: str | None = None,
    ):
        self.retry_reason = retry_reason
        self.retry_after = retry_after
        if message is None:
            message = f"Collector execution failed ({retry_reason}), retry later"
        super().__init__(message)


class CollectorRegistry:
    """注册中心: 管理所有 Collector 实例 (单例风格)."""

    def __init__(self):
        self._collectors: dict[str, Any] = {}

    def register(self, collector: Any):
        if collector.name in self._collectors:
            raise ValueError(f"collector already registered: {collector.name}")
        self._collectors[collector.name] = collector

    def get(self, name: str) -> Any:
        return self._collectors[name]

    def all(self) -> list[Any]:
        return list(self._collectors.values())


registry = CollectorRegistry()
