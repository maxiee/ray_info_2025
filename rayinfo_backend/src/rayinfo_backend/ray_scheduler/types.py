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

    简化后的命名风格（不再区分任何任务类型）：
    - 普通采集器:  "<collector>"
    - 参数化采集器: "<collector>:<param>"
    - 配额重试:    与普通采集器格式相同

    Args:
        collector_name: 采集器名称
        param: 参数化采集器的参数，普通采集器为 None
        kind: 任务类型（不再影响 ID 生成）
        suffix: 可选后缀（例如时间戳）

    Returns:
        任务 ID 字符串
    """

    parts: list[str] = [collector_name]
    if param is not None:
        parts.append(str(param))
    
    # 不再添加任何任务类型标识
    if suffix:
        parts.append(suffix)
    return ":".join(parts)
