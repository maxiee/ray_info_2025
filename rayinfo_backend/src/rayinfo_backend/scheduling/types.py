from __future__ import annotations

from enum import Enum
from typing import Optional


class JobKind(str, Enum):
    """Job 类型枚举，用于统一生成任务 ID。

    - initial: 初始（一次性）执行
    - periodic: 周期性执行
    - quota_retry: 因配额导致的延迟重试
    """

    Initial = "initial"
    Periodic = "periodic"
    QuotaRetry = "quota_retry"


def make_job_id(
    collector_name: str,
    param: Optional[str],
    kind: JobKind,
    *,
    suffix: Optional[str] = None,
) -> str:
    """生成统一格式的 APScheduler job id。

    兼容既有命名风格：
    - 普通采集器:  "<collector>:initial" / "<collector>:periodic"
    - 参数化采集器: "<collector>:<param>:initial" / "<collector>:<param>:periodic"
    - 配额重试:    在上述基础上使用 "quota_retry"，并可附加时间戳后缀以确保唯一

    Args:
        collector_name: 采集器名称
        param: 参数化采集器的参数，普通采集器为 None
        kind: 任务类型
        suffix: 可选后缀（例如时间戳）

    Returns:
        任务 ID 字符串
    """

    parts: list[str] = [collector_name]
    if param is not None:
        parts.append(str(param))
    parts.append(kind.value)
    if suffix:
        parts.append(suffix)
    return ":".join(parts)
