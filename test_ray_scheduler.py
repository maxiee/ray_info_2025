#!/usr/bin/env python3
"""测试新的 RayScheduler 调度器功能"""

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# 导入测试需要的模块
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "rayinfo_backend/src"))

# 只导入核心调度器组件，避免复杂依赖
from rayinfo_backend.ray_scheduler.task import Task
from rayinfo_backend.ray_scheduler.consumer import BaseTaskConsumer
from rayinfo_backend.ray_scheduler.registry import registry
from rayinfo_backend.ray_scheduler.scheduler import RayScheduler

logger = logging.getLogger("test_ray_scheduler")


class TestTaskConsumer(BaseTaskConsumer):
    """测试用的任务消费者"""

    def __init__(self, name: str, concurrent_count: int = 1, delay: float = 0.1):
        super().__init__(name, concurrent_count)
        self.delay = delay
        self.executed_tasks = []
        self.execution_times = []

    def produce(self, args: Optional[Dict[str, Any]] = None) -> Task:
        """生产任务"""
        return Task(
            source=self.name,
            args=args or {},
            schedule_at=args.get("schedule_at") if args else None,
        )

    async def consume(self, task: Task) -> None:
        """消费任务"""
        start_time = time.time()
        logger.info(f"[{self.name}] 开始执行任务 {task.uuid[:8]}")

        # 模拟任务执行时间
        await asyncio.sleep(self.delay)

        end_time = time.time()
        self.executed_tasks.append(task)
        self.execution_times.append(end_time)

        logger.info(
            f"[{self.name}] 完成任务 {task.uuid[:8]} (耗时 {end_time - start_time:.2f}s)"
        )


class ErrorTaskConsumer(TestTaskConsumer):
    """会抛出异常的任务消费者"""

    async def consume(self, task: Task) -> None:
        logger.info(f"[{self.name}] 执行任务 {task.uuid[:8]} - 即将抛出异常")
        raise RuntimeError(f"测试异常来自 {self.name}")


async def test_basic_scheduling():
    """测试基本调度功能"""
    logger.info("=== 测试基本调度功能 ===")

    # 清空注册表
    registry.clear()

    # 创建调度器
    scheduler = RayScheduler()

    # 创建测试消费者
    consumer = TestTaskConsumer("test.basic", concurrent_count=1, delay=0.1)
    registry.register(consumer)

    # 启动调度器
    await scheduler.start()

    try:
        # 创建立即执行的任务
        task1 = consumer.produce({"message": "task1"})
        task2 = consumer.produce({"message": "task2"})

        # 添加任务
        scheduler.add_task(task1)
        scheduler.add_task(task2)

        # 等待任务完成
        await asyncio.sleep(0.5)

        # 验证结果
        assert len(consumer.executed_tasks) == 2
        logger.info("✓ 基本调度测试通过")

    finally:
        await scheduler.stop()


async def test_time_ordering():
    """测试时间顺序调度"""
    logger.info("=== 测试时间顺序调度 ===")

    # 清空注册表
    registry.clear()

    # 创建调度器
    scheduler = RayScheduler()

    # 创建测试消费者
    consumer = TestTaskConsumer("test.ordering", concurrent_count=1, delay=0.05)
    registry.register(consumer)

    # 启动调度器
    await scheduler.start()

    try:
        now = datetime.now(timezone.utc)

        # 创建不同时间的任务（故意倒序添加）
        task3 = consumer.produce(
            {"message": "task3", "schedule_at": now + timedelta(seconds=0.3)}
        )
        task1 = consumer.produce(
            {"message": "task1", "schedule_at": now + timedelta(seconds=0.1)}
        )
        task2 = consumer.produce(
            {"message": "task2", "schedule_at": now + timedelta(seconds=0.2)}
        )

        # 倒序添加任务
        scheduler.add_task(task3)
        scheduler.add_task(task1)
        scheduler.add_task(task2)

        # 等待任务完成
        await asyncio.sleep(0.6)

        # 验证执行顺序
        assert len(consumer.executed_tasks) == 3

        # 检查执行时间顺序
        execution_order = [task.args["message"] for task in consumer.executed_tasks]
        assert execution_order == ["task1", "task2", "task3"]

        logger.info("✓ 时间顺序调度测试通过")

    finally:
        await scheduler.stop()


async def test_early_task_insertion():
    """测试更早任务插队唤醒"""
    logger.info("=== 测试更早任务插队唤醒 ===")

    # 清空注册表
    registry.clear()

    # 创建调度器
    scheduler = RayScheduler()

    # 创建测试消费者
    consumer = TestTaskConsumer("test.insertion", concurrent_count=1, delay=0.05)
    registry.register(consumer)

    # 启动调度器
    await scheduler.start()

    try:
        now = datetime.now(timezone.utc)

        # 先添加一个较晚的任务
        late_task = consumer.produce(
            {"message": "late_task", "schedule_at": now + timedelta(seconds=0.5)}
        )
        scheduler.add_task(late_task)

        # 等待一小段时间确保调度器在等待
        await asyncio.sleep(0.1)

        # 插入一个更早的任务
        early_task = consumer.produce(
            {"message": "early_task", "schedule_at": now + timedelta(seconds=0.2)}
        )
        scheduler.add_task(early_task)

        # 等待任务完成
        await asyncio.sleep(0.7)

        # 验证执行顺序
        assert len(consumer.executed_tasks) == 2
        execution_order = [task.args["message"] for task in consumer.executed_tasks]
        assert execution_order == ["early_task", "late_task"]

        logger.info("✓ 更早任务插队唤醒测试通过")

    finally:
        await scheduler.stop()


async def test_concurrent_control():
    """测试并发控制"""
    logger.info("=== 测试并发控制 ===")

    # 清空注册表
    registry.clear()

    # 创建调度器
    scheduler = RayScheduler()

    # 创建并发数为2的消费者
    consumer = TestTaskConsumer("test.concurrent", concurrent_count=2, delay=0.2)
    registry.register(consumer)

    # 启动调度器
    await scheduler.start()

    try:
        # 创建多个立即执行的任务
        tasks = []
        for i in range(4):
            task = consumer.produce({"message": f"task{i+1}"})
            tasks.append(task)
            scheduler.add_task(task)

        # 等待一段时间，检查并发控制
        await asyncio.sleep(0.1)  # 在第一批任务还在执行时检查

        # 第一批应该有2个任务在执行
        await asyncio.sleep(0.15)  # 等待第一批完成

        # 第二批应该开始执行
        await asyncio.sleep(0.25)  # 等待所有任务完成

        # 验证所有任务都执行了
        assert len(consumer.executed_tasks) == 4

        # 验证执行时间模式（证明并发控制生效）
        execution_times = consumer.execution_times

        # 前两个任务应该几乎同时完成
        assert abs(execution_times[1] - execution_times[0]) < 0.1

        # 后两个任务应该在前两个任务完成后执行
        assert execution_times[2] > execution_times[1]

        logger.info("✓ 并发控制测试通过")

    finally:
        await scheduler.stop()


async def test_error_handling():
    """测试错误处理"""
    logger.info("=== 测试错误处理 ===")

    # 清空注册表
    registry.clear()

    # 创建调度器
    scheduler = RayScheduler()

    # 创建正常消费者和错误消费者
    normal_consumer = TestTaskConsumer("test.normal", delay=0.05)
    error_consumer = ErrorTaskConsumer("test.error", delay=0.05)

    registry.register(normal_consumer)
    registry.register(error_consumer)

    # 启动调度器
    await scheduler.start()

    try:
        # 创建任务
        normal_task = normal_consumer.produce({"message": "normal"})
        error_task = error_consumer.produce({"message": "error"})
        another_normal_task = normal_consumer.produce({"message": "another_normal"})

        # 添加任务
        scheduler.add_task(normal_task)
        scheduler.add_task(error_task)
        scheduler.add_task(another_normal_task)

        # 等待任务完成
        await asyncio.sleep(0.3)

        # 验证正常任务执行了，错误任务被记录但不影响其他任务
        assert len(normal_consumer.executed_tasks) == 2
        assert len(error_consumer.executed_tasks) == 0  # 因为抛出异常，不会记录

        logger.info("✓ 错误处理测试通过")

    finally:
        await scheduler.stop()


async def test_unknown_source():
    """测试未知源处理"""
    logger.info("=== 测试未知源处理 ===")

    # 清空注册表
    registry.clear()

    # 创建调度器
    scheduler = RayScheduler()

    # 启动调度器
    await scheduler.start()

    try:
        # 创建未知源的任务
        unknown_task = Task(
            source="unknown.source",
            args={"message": "unknown"},
        )

        # 添加任务
        scheduler.add_task(unknown_task)

        # 等待处理
        await asyncio.sleep(0.2)

        # 任务应该被丢弃，但不会导致调度器崩溃
        assert scheduler.is_running()

        logger.info("✓ 未知源处理测试通过")

    finally:
        await scheduler.stop()


async def test_past_time_tasks():
    """测试过去时间任务立即执行"""
    logger.info("=== 测试过去时间任务立即执行 ===")

    # 清空注册表
    registry.clear()

    # 创建调度器
    scheduler = RayScheduler()

    # 创建测试消费者
    consumer = TestTaskConsumer("test.past", delay=0.05)
    registry.register(consumer)

    # 启动调度器
    await scheduler.start()

    try:
        # 创建过去时间的任务
        past_time = datetime.now(timezone.utc) - timedelta(seconds=1)
        past_task = consumer.produce({"message": "past_task", "schedule_at": past_time})

        # 添加任务
        scheduler.add_task(past_task)

        # 等待任务完成
        await asyncio.sleep(0.2)

        # 验证任务立即执行了
        assert len(consumer.executed_tasks) == 1

        logger.info("✓ 过去时间任务立即执行测试通过")

    finally:
        await scheduler.stop()


async def run_all_tests():
    """运行所有测试"""
    logger.info("开始运行 RayScheduler 测试套件")

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
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
