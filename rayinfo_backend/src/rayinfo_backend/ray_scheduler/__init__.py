"""RayScheduler 组件集合

包含 RayInfo 后端的调度相关基础设施：
- Task: 调度的最小单元
- BaseTaskConsumer: 任务消费者基类
- TaskConsumerRegistry: 统一的任务注册表
- RayScheduler: 基于 1s tick 的简化调度器
- TaskExecutionManager: 任务执行记录管理
- JobKind / make_job_id: 任务 ID 辅助工具

当前实现强调数据驱动与可读性，任务在启动时加载入内存字典，
由定时循环按需触发执行。
"""

from .task import Task
from .consumer import BaseTaskConsumer
from .registry import TaskConsumerRegistry, registry
from .scheduler import RayScheduler
from .execution_manager import TaskExecutionManager
from .types import JobKind, make_job_id

__all__ = [
    "Task",
    "BaseTaskConsumer",
    "TaskConsumerRegistry",
    "registry",
    "RayScheduler",
    "TaskExecutionManager",
    "JobKind",
    "make_job_id",
]
