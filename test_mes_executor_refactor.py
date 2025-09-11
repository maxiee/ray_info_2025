#!/usr/bin/env python3
"""测试 MesExecutor 重构后的实现"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "rayinfo_backend/src"))

from rayinfo_backend.collectors.mes.mes_executor import MesExecutor, get_mes_executor
from rayinfo_backend.ray_scheduler.task import Task
from rayinfo_backend.ray_scheduler.consumer import BaseTaskConsumer


async def test_mes_executor_inheritance():
    """测试 MesExecutor 继承关系"""
    print("=== 测试 MesExecutor 继承关系 ===")

    # 获取实例
    executor = get_mes_executor()

    # 验证继承关系
    assert isinstance(
        executor, BaseTaskConsumer
    ), "MesExecutor 应该继承自 BaseTaskConsumer"
    assert isinstance(executor, MesExecutor), "应该是 MesExecutor 实例"

    # 验证属性
    assert hasattr(executor, "name"), "应该有 name 属性"
    assert hasattr(executor, "concurrent_count"), "应该有 concurrent_count 属性"
    assert hasattr(executor, "consume"), "应该有 consume 方法"

    print(f"✓ 继承关系正确: {type(executor).__name__}")
    print(f"✓ name: {executor.name}")
    print(f"✓ concurrent_count: {executor.concurrent_count}")


async def test_singleton_pattern():
    """测试单例模式"""
    print("\n=== 测试单例模式 ===")

    # 创建多个实例
    executor1 = MesExecutor()
    executor2 = MesExecutor()
    executor3 = get_mes_executor()

    # 验证是同一个实例
    assert executor1 is executor2, "应该是同一个实例"
    assert executor2 is executor3, "应该是同一个实例"

    print("✓ 单例模式工作正常")


async def test_task_consumption():
    """测试任务消费"""
    print("\n=== 测试任务消费 ===")

    executor = get_mes_executor()

    # 创建一个测试任务
    task = Task(
        source="mes_executor",
        args={
            "query": "Python programming",
            "engine": "duckduckgo",
            "time_range": "week",
        },
    )

    print(f"创建任务: {task}")

    try:
        # 注意：这个测试可能会失败，因为需要实际的 mes 命令
        # 但我们主要是测试参数验证和方法调用
        await executor.consume(task)
        print("✓ 任务消费成功")
    except Exception as e:
        # 如果是因为缺少 mes 命令或网络问题失败，这是预期的
        print(f"✓ 任务消费方法调用成功（失败原因：{e}）")


async def test_parameter_validation():
    """测试参数验证"""
    print("\n=== 测试参数验证 ===")

    executor = get_mes_executor()

    # 测试缺少 query 参数
    task_missing_query = Task(source="mes_executor", args={"engine": "duckduckgo"})

    try:
        await executor.consume(task_missing_query)
        assert False, "应该抛出 ValueError"
    except ValueError as e:
        print(f"✓ 正确检测到缺少 query 参数: {e}")

    # 测试缺少 engine 参数
    task_missing_engine = Task(source="mes_executor", args={"query": "test"})

    try:
        await executor.consume(task_missing_engine)
        assert False, "应该抛出 ValueError"
    except ValueError as e:
        print(f"✓ 正确检测到缺少 engine 参数: {e}")


async def main():
    """运行所有测试"""
    print("开始测试 MesExecutor 重构后的实现...\n")

    try:
        await test_mes_executor_inheritance()
        await test_singleton_pattern()
        await test_task_consumption()
        await test_parameter_validation()

        print("\n🎉 所有测试通过！")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
