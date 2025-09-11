"""RayScheduler: 基于 AsyncIO 的异步任务调度器"""

from __future__ import annotations

import asyncio
import heapq
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .task import Task
from .registry import registry


class RayScheduler:
    """基于 AsyncIO 的异步任务调度器
    
    负责基于 AsyncIO 对 Task 进行时间驱动与并发受控的异步调度。
    
    核心目标：
    - 按 Task.schedule_at 顺序触发任务（最早优先）
    - 按 Task.source 的并发上限进行限流
    - 空闲时不忙等，新任务/更早任务到来时可被立即唤醒
    - 失败任务最小实现仅记录日志，不做重试
    
    核心数据结构：
    - heap: 最小堆队列，按触发时间排序
    - event: 唤醒事件，用于可中断等待
    - _sem_by_source: 源级并发控制信号量
    """
    
    def __init__(self):
        """初始化调度器"""
        # 内部堆队列（最小触发时间优先）
        # 结构：(when_ts: float, seq: int, task: Task)
        self._heap: List[Tuple[float, int, Task]] = []
        
        # 唤醒事件：有更早/新任务加入或需要重算下一次唤醒时间时置位
        self._event = asyncio.Event()
        
        # 源级并发控制
        self._sem_by_source: Dict[str, asyncio.Semaphore] = {}
        
        # 运行状态
        self._running = False
        self._task_dispatcher: Optional[asyncio.Task] = None
        
        # 序列号（确保同一触发时间下的稳定出队顺序）
        self._seq = 0
        
        # 日志记录器
        self._log = logging.getLogger("rayinfo.ray_scheduler")
    
    def add_task(self, task: Task) -> None:
        """向调度器提交一个待执行任务
        
        Args:
            task: 待执行的任务
        """
        # 计算 UTC 时间戳
        when_ts = task.schedule_at.astimezone(timezone.utc).timestamp()
        
        # 添加到堆中
        heapq.heappush(self._heap, (when_ts, self._seq, task))
        self._seq += 1
        
        # 唤醒调度器主循环（可能出现"更早任务插队"）
        self._event.set()
        
        self._log.debug(
            "Added task to scheduler: %s (schedule_at=%s, queue_size=%d)",
            task,
            task.schedule_at,
            len(self._heap)
        )
    
    async def start(self) -> None:
        """启动调度器主循环（幂等）"""
        if self._running:
            self._log.warning("Scheduler already running")
            return
        
        self._running = True
        self._task_dispatcher = asyncio.create_task(self._dispatcher_loop())
        self._log.info("Scheduler started")
    
    async def stop(self) -> None:
        """有序停止调度器"""
        if not self._running:
            self._log.warning("Scheduler not running")
            return
        
        # 停止主循环
        self._running = False
        
        # 唤醒主循环以打断阻塞等待
        self._event.set()
        
        # 等待主循环自然退出
        if self._task_dispatcher:
            await self._task_dispatcher
            self._task_dispatcher = None
        
        self._log.info("Scheduler stopped")
    
    def _get_sem(self, source: str) -> asyncio.Semaphore:
        """获取或创建源级并发控制信号量（懒创建）
        
        Args:
            source: 任务源名称
            
        Returns:
            对应的信号量
        """
        if source not in self._sem_by_source:
            # 从注册表获取并发数
            task_consumer = registry.find(source)
            concurrent_count = task_consumer.concurrent_count if task_consumer else 1
            
            self._sem_by_source[source] = asyncio.Semaphore(concurrent_count)
            self._log.debug(
                "Created semaphore for source '%s' with concurrent_count=%d",
                source,
                concurrent_count
            )
        
        return self._sem_by_source[source]
    
    async def _dispatcher_loop(self) -> None:
        """调度器主循环：时间驱动 + 唤醒可中断等待 + 触发任务"""
        try:
            self._log.info("Scheduler main loop started")
            
            while self._running:
                if not self._heap:
                    # 堆为空，等待新任务到来
                    self._event.clear()
                    await self._event.wait()
                    continue
                
                # 窥视堆顶（只查看，不弹出）
                when, _, task = self._heap[0]
                now = datetime.now(timezone.utc).timestamp()
                delay = max(0, when - now)
                
                if delay > 0:
                    # 未到触发时间，二选一等待
                    self._event.clear()
                    
                    try:
                        # 等待时间到点或有更早任务插入
                        await asyncio.wait_for(self._event.wait(), timeout=delay)
                        # 如果是因为事件唤醒，重新计算堆顶与延迟
                        continue
                    except asyncio.TimeoutError:
                        # 时间到点，继续处理
                        pass
                
                # 到点：弹出任务并触发执行
                heapq.heappop(self._heap)
                
                # 创建执行协程（不阻塞主循环）
                asyncio.create_task(self._run_task_once(task))
        
        except Exception as e:
            self._log.exception("Scheduler main loop error: %s", e)
        finally:
            self._log.info("Scheduler main loop stopped")
    
    async def _run_task_once(self, task: Task) -> None:
        """执行单个任务的业务消费，并遵循源级并发上限
        
        Args:
            task: 要执行的任务
        """
        # 查找 TaskConsumer
        src = registry.find(task.source)
        if src is None:
            self._log.error(
                "[drop] Unknown task source: %s %s",
                task.source,
                task.to_dict()
            )
            return
        
        # 获取源级信号量
        sem = self._get_sem(task.source)
        
        # 执行任务（遵循并发控制）
        await sem.acquire()
        try:
            self._log.debug("Executing task: %s", task)
            await src.consume(task)
            self._log.debug("Task completed successfully: %s", task)
        except Exception as e:
            self._log.exception(
                "[fail] task %s from %s: %s",
                task.uuid,
                task.source,
                e
            )
        finally:
            sem.release()
    
    def get_queue_size(self) -> int:
        """获取当前队列中的任务数量
        
        Returns:
            队列中等待执行的任务数量
        """
        return len(self._heap)
    
    def is_running(self) -> bool:
        """检查调度器是否正在运行
        
        Returns:
            如果调度器正在运行返回 True，否则返回 False
        """
        return self._running
    
    def get_next_task_time(self) -> Optional[datetime]:
        """获取下一个要执行的任务时间
        
        Returns:
            下一个任务的执行时间，如果队列为空返回 None
        """
        if not self._heap:
            return None
        
        when, _, _ = self._heap[0]
        return datetime.fromtimestamp(when, timezone.utc)