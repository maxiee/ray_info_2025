"""RayScheduler: 基于 AsyncIO 的异步任务调度框架

主要组件:
- Task: 调度的最小单元
- BaseTaskConsumer: 任务生产者/消费者基类  
- TaskConsumerRegistry: 任务消费者注册表
- RayScheduler: 核心调度器
- CollectorTaskConsumer: 采集器适配器
- CollectorStateManager: 状态管理器
- JobKind, make_job_id: 任务类型和ID生成

核心特性:
- 基于 asyncio 的时间驱动调度
- 源级并发控制
- 最小堆实现的优先级队列
- 可中断的等待机制
- 失败任务日志记录
"""

from .task import Task
from .consumer import BaseTaskConsumer
from .registry import TaskConsumerRegistry, registry
from .scheduler import RayScheduler
from .adapters import CollectorTaskConsumer, create_collector_consumer
from .state_manager import CollectorStateManager
from .types import JobKind, make_job_id

__all__ = [
    "Task",
    "BaseTaskConsumer", 
    "TaskConsumerRegistry",
    "registry",
    "RayScheduler",
    "CollectorTaskConsumer",
    "create_collector_consumer",
    "CollectorStateManager",
    "JobKind",
    "make_job_id",
]