#!/usr/bin/env python3
"""测试新的 RayScheduler 调度器核心功能（无外部依赖）"""

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod
import uuid as uuid_lib
import heapq

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger("test_ray_scheduler_core")


# 直接复制核心类，避免导入依赖问题
class Task:
    """任务类 - 调度器调度的最小单元"""

    def __init__(
        self,
        source: str,
        args: Optional[Dict[str, Any]] = None,
        schedule_at: Optional[datetime] = None,
        uuid: Optional[str] = None,
    ):
        self.uuid = uuid or str(uuid_lib.uuid4())
        self.args = args or {}
        self.source = source
        self.schedule_at = schedule_at or datetime.now(timezone.utc)

        if self.schedule_at.tzinfo is None:
            self.schedule_at = self.schedule_at.replace(tzinfo=timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "args": self.args,
            "source": self.source,
            "schedule_at": self.schedule_at.isoformat(),
        }

    def __str__(self) -> str:
        return f"Task(uuid={self.uuid[:8]}, source={self.source}, schedule_at={self.schedule_at})"


class BaseTaskConsumer(ABC):
    """任务生产者/消费者基类"""

    def __init__(self, name: str, concurrent_count: int = 1):
        self.name = name
        self.concurrent_count = max(1, concurrent_count)

    @abstractmethod
    def produce(self, args: Optional[Dict[str, Any]] = None) -> Task:
        raise NotImplementedError

    @abstractmethod
    async def consume(self, task: Task) -> None:
        raise NotImplementedError


class TaskConsumerRegistry:
    """任务消费者注册表"""

    def __init__(self):
        self.sources: Dict[str, BaseTaskConsumer] = {}

    def register(self, source: BaseTaskConsumer) -> None:
        if source.name in self.sources:
            raise ValueError(
                f"TaskConsumer with name '{source.name}' already registered"
            )
        self.sources[source.name] = source

    def find(self, name: str) -> Optional[BaseTaskConsumer]:
        return self.sources.get(name)

    def clear(self) -> None:
        self.sources.clear()


class RayScheduler:
    """基于 AsyncIO 的异步任务调度器"""

    def __init__(self, registry: TaskConsumerRegistry):
        self._heap = []
        self._event = asyncio.Event()
        self._sem_by_source = {}
        self._running = False
        self._task_dispatcher = None
        self._seq = 0
        self._registry = registry
        self._log = logging.getLogger("rayinfo.ray_scheduler")

    def add_task(self, task: Task) -> None:
        when_ts = task.schedule_at.astimezone(timezone.utc).timestamp()
        heapq.heappush(self._heap, (when_ts, self._seq, task))
        self._seq += 1
        self._event.set()

        self._log.debug(
            "Added task to scheduler: %s (schedule_at=%s, queue_size=%d)",
            task,
            task.schedule_at,
            len(self._heap),
        )

    async def start(self) -> None:
        if self._running:
            self._log.warning("Scheduler already running")
            return

        self._running = True
        self._task_dispatcher = asyncio.create_task(self._dispatcher_loop())
        self._log.info("Scheduler started")

    async def stop(self) -> None:
        if not self._running:
            self._log.warning("Scheduler not running")
            return

        self._running = False
        self._event.set()

        if self._task_dispatcher:
            await self._task_dispatcher
            self._task_dispatcher = None

        self._log.info("Scheduler stopped")

    def _get_sem(self, source: str) -> asyncio.Semaphore:
        if source not in self._sem_by_source:
            task_consumer = self._registry.find(source)
            concurrent_count = task_consumer.concurrent_count if task_consumer else 1

            self._sem_by_source[source] = asyncio.Semaphore(concurrent_count)
            self._log.debug(
                "Created semaphore for source '%s' with concurrent_count=%d",
                source,
                concurrent_count,
            )

        return self._sem_by_source[source]

    async def _dispatcher_loop(self) -> None:
        try:
            self._log.info("Scheduler main loop started")

            while self._running:
                if not self._heap:
                    self._event.clear()
                    await self._event.wait()
                    continue

                when, _, task = self._heap[0]
                now = datetime.now(timezone.utc).timestamp()
                delay = max(0, when - now)

                if delay > 0:
                    self._event.clear()

                    try:
                        await asyncio.wait_for(self._event.wait(), timeout=delay)
                        continue
                    except asyncio.TimeoutError:
                        pass

                heapq.heappop(self._heap)
                asyncio.create_task(self._run_task_once(task))

        except Exception as e:
            self._log.exception("Scheduler main loop error: %s", e)
        finally:
            self._log.info("Scheduler main loop stopped")

    async def _run_task_once(self, task: Task) -> None:
        src = self._registry.find(task.source)
        if src is None:
            self._log.error(
                "[drop] Unknown task source: %s %s", task.source, task.to_dict()
            )
            return

        sem = self._get_sem(task.source)

        await sem.acquire()
        try:
            self._log.debug("Executing task: %s", task)
            await src.consume(task)
            self._log.debug("Task completed successfully: %s", task)
        except Exception as e:
            self._log.exception("[fail] task %s from %s: %s", task.uuid, task.source, e)
        finally:
            sem.release()

    def get_queue_size(self) -> int:
        return len(self._heap)

    def is_running(self) -> bool:
        return self._running


# 测试用的任务消费者
class TestTaskConsumer(BaseTaskConsumer):
    def __init__(self, name: str, concurrent_count: int = 1, delay: float = 0.1):
        super().__init__(name, concurrent_count)
        self.delay = delay
        self.executed_tasks = []
        self.execution_times = []

    def produce(self, args: Optional[Dict[str, Any]] = None) -> Task:
        return Task(
            source=self.name,
            args=args or {},
            schedule_at=args.get("schedule_at") if args else None,
        )

    async def consume(self, task: Task) -> None:
        start_time = time.time()
        logger.info(f"[{self.name}] 开始执行任务 {task.uuid[:8]}")

        await asyncio.sleep(self.delay)

        end_time = time.time()
        self.executed_tasks.append(task)
        self.execution_times.append(end_time)

        logger.info(
            f"[{self.name}] 完成任务 {task.uuid[:8]} (耗时 {end_time - start_time:.2f}s)"
        )


class ErrorTaskConsumer(TestTaskConsumer):
    async def consume(self, task: Task) -> None:
        logger.info(f"[{self.name}] 执行任务 {task.uuid[:8]} - 即将抛出异常")
        raise RuntimeError(f"测试异常来自 {self.name}")


# 测试函数
async def test_basic_scheduling():
    """测试基本调度功能"""
    logger.info("=== 测试基本调度功能 ===")

    registry = TaskConsumerRegistry()
    scheduler = RayScheduler(registry)

    consumer = TestTaskConsumer("test.basic", concurrent_count=1, delay=0.1)
    registry.register(consumer)

    await scheduler.start()

    try:
        task1 = consumer.produce({"message": "task1"})
        task2 = consumer.produce({"message": "task2"})

        scheduler.add_task(task1)
        scheduler.add_task(task2)

        await asyncio.sleep(0.5)

        assert len(consumer.executed_tasks) == 2
        logger.info("✓ 基本调度测试通过")

    finally:
        await scheduler.stop()


async def test_time_ordering():
    """测试时间顺序调度"""
    logger.info("=== 测试时间顺序调度 ===")

    registry = TaskConsumerRegistry()
    scheduler = RayScheduler(registry)

    consumer = TestTaskConsumer("test.ordering", concurrent_count=1, delay=0.05)
    registry.register(consumer)

    await scheduler.start()

    try:
        now = datetime.now(timezone.utc)

        task3 = consumer.produce(
            {"message": "task3", "schedule_at": now + timedelta(seconds=0.3)}
        )
        task1 = consumer.produce(
            {"message": "task1", "schedule_at": now + timedelta(seconds=0.1)}
        )
        task2 = consumer.produce(
            {"message": "task2", "schedule_at": now + timedelta(seconds=0.2)}
        )

        scheduler.add_task(task3)
        scheduler.add_task(task1)
        scheduler.add_task(task2)

        await asyncio.sleep(0.6)

        assert len(consumer.executed_tasks) == 3

        execution_order = [task.args["message"] for task in consumer.executed_tasks]
        assert execution_order == ["task1", "task2", "task3"]

        logger.info("✓ 时间顺序调度测试通过")

    finally:
        await scheduler.stop()


async def test_early_task_insertion():
    """测试更早任务插队唤醒"""
    logger.info("=== 测试更早任务插队唤醒 ===")

    registry = TaskConsumerRegistry()
    scheduler = RayScheduler(registry)

    consumer = TestTaskConsumer("test.insertion", concurrent_count=1, delay=0.05)
    registry.register(consumer)

    await scheduler.start()

    try:
        now = datetime.now(timezone.utc)

        late_task = consumer.produce(
            {"message": "late_task", "schedule_at": now + timedelta(seconds=0.5)}
        )
        scheduler.add_task(late_task)

        await asyncio.sleep(0.1)

        early_task = consumer.produce(
            {"message": "early_task", "schedule_at": now + timedelta(seconds=0.2)}
        )
        scheduler.add_task(early_task)

        await asyncio.sleep(0.7)

        assert len(consumer.executed_tasks) == 2
        execution_order = [task.args["message"] for task in consumer.executed_tasks]
        assert execution_order == ["early_task", "late_task"]

        logger.info("✓ 更早任务插队唤醒测试通过")

    finally:
        await scheduler.stop()


async def test_concurrent_control():
    """测试并发控制"""
    logger.info("=== 测试并发控制 ===")

    registry = TaskConsumerRegistry()
    scheduler = RayScheduler(registry)

    consumer = TestTaskConsumer("test.concurrent", concurrent_count=2, delay=0.2)
    registry.register(consumer)

    await scheduler.start()

    try:
        tasks = []
        for i in range(4):
            task = consumer.produce({"message": f"task{i+1}"})
            tasks.append(task)
            scheduler.add_task(task)

        await asyncio.sleep(0.1)
        await asyncio.sleep(0.15)
        await asyncio.sleep(0.25)

        assert len(consumer.executed_tasks) == 4

        execution_times = consumer.execution_times
        assert abs(execution_times[1] - execution_times[0]) < 0.1
        assert execution_times[2] > execution_times[1]

        logger.info("✓ 并发控制测试通过")

    finally:
        await scheduler.stop()


async def test_error_handling():
    """测试错误处理"""
    logger.info("=== 测试错误处理 ===")

    registry = TaskConsumerRegistry()
    scheduler = RayScheduler(registry)

    normal_consumer = TestTaskConsumer("test.normal", delay=0.05)
    error_consumer = ErrorTaskConsumer("test.error", delay=0.05)

    registry.register(normal_consumer)
    registry.register(error_consumer)

    await scheduler.start()

    try:
        normal_task = normal_consumer.produce({"message": "normal"})
        error_task = error_consumer.produce({"message": "error"})
        another_normal_task = normal_consumer.produce({"message": "another_normal"})

        scheduler.add_task(normal_task)
        scheduler.add_task(error_task)
        scheduler.add_task(another_normal_task)

        await asyncio.sleep(0.3)

        assert len(normal_consumer.executed_tasks) == 2
        assert len(error_consumer.executed_tasks) == 0

        logger.info("✓ 错误处理测试通过")

    finally:
        await scheduler.stop()


async def test_unknown_source():
    """测试未知源处理"""
    logger.info("=== 测试未知源处理 ===")

    registry = TaskConsumerRegistry()
    scheduler = RayScheduler(registry)

    await scheduler.start()

    try:
        unknown_task = Task(
            source="unknown.source",
            args={"message": "unknown"},
        )

        scheduler.add_task(unknown_task)

        await asyncio.sleep(0.2)

        assert scheduler.is_running()

        logger.info("✓ 未知源处理测试通过")

    finally:
        await scheduler.stop()


async def test_past_time_tasks():
    """测试过去时间任务立即执行"""
    logger.info("=== 测试过去时间任务立即执行 ===")

    registry = TaskConsumerRegistry()
    scheduler = RayScheduler(registry)

    consumer = TestTaskConsumer("test.past", delay=0.05)
    registry.register(consumer)

    await scheduler.start()

    try:
        past_time = datetime.now(timezone.utc) - timedelta(seconds=1)
        past_task = consumer.produce({"message": "past_task", "schedule_at": past_time})

        scheduler.add_task(past_task)

        await asyncio.sleep(0.2)

        assert len(consumer.executed_tasks) == 1

        logger.info("✓ 过去时间任务立即执行测试通过")

    finally:
        await scheduler.stop()


async def run_all_tests():
    """运行所有测试"""
    logger.info("开始运行 RayScheduler 核心功能测试套件")

    tests = [
        test_basic_scheduling,
        test_time_ordering,
        test_early_task_insertion,
        test_concurrent_control,
        test_error_handling,
        test_unknown_source,
        test_past_time_tasks,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            await test()
            passed += 1
        except Exception as e:
            logger.error(f"测试失败 {test.__name__}: {e}")
            failed += 1

    logger.info(f"测试完成: {passed} 通过, {failed} 失败")

    if failed == 0:
        logger.info("🎉 所有测试通过！")
    else:
        logger.error(f"❌ {failed} 个测试失败")

    return failed == 0


if __name__ == "__main__":
    import sys

    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
