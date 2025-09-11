#!/usr/bin/env python3
"""测试 MesExecutor 重构后的实现"""

import asyncio
import sys

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
    print(
        f"✓ 父类方法: {hasattr(executor, '__str__')}, {hasattr(executor, '__repr__')}"
    )


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


async def test_task_creation_and_structure():
    """测试任务创建和结构"""
    print("\n=== 测试任务创建和结构 ===")

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

    print(f"✓ 任务创建成功: {task}")
    print(f"✓ 任务字典格式: {task.to_dict()}")

    # 测试 str 和 repr 方法
    print(f"✓ 执行器字符串表示: {str(executor)}")
    print(f"✓ 执行器详细表示: {repr(executor)}")


async def main():
    """运行所有测试"""
    print("开始测试 MesExecutor 重构后的实现...\n")

    try:
        await test_mes_executor_inheritance()
        await test_singleton_pattern()
        await test_parameter_validation()
        await test_task_creation_and_structure()

        print("\n🎉 所有基础测试通过！")
        print("\n注意: 实际的 mes 命令执行需要安装 mes CLI 工具和网络连接。")
        print("这里主要测试了继承关系、单例模式和参数验证等核心功能。")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
