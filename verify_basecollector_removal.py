#!/usr/bin/env python3
"""验证 BaseCollector 移除的简单测试"""

import sys
import os

# 添加src路径到PYTHONPATH
sys.path.insert(0, "/Volumes/ssd/Code/ray_info_2025/rayinfo_backend/src")


def test_basecollector_removal():
    """测试 BaseCollector 是否已经被成功移除"""

    print("=== 验证 BaseCollector 移除 ===")

    # 1. 测试从 base 模块导入 BaseCollector 会失败
    try:
        from rayinfo_backend.collectors.base import BaseCollector

        print("❌ 错误：BaseCollector 仍然存在")
        return False
    except ImportError:
        print("✓ BaseCollector 已成功移除")

    # 2. 测试其他类仍然可用
    try:
        from rayinfo_backend.collectors.base import (
            RawEvent,
            CollectorError,
            CollectorRetryableException,
            CollectorRegistry,
        )

        print(
            "✓ 其他必要的类仍然可用：RawEvent, CollectorError, CollectorRetryableException, CollectorRegistry"
        )
    except ImportError as e:
        print(f"❌ 错误：必要的类缺失 - {e}")
        return False

    # 3. 测试 RawEvent 可以正常创建
    try:
        event = RawEvent(source="test", raw={"data": "test"})
        print("✓ RawEvent 可以正常创建")
    except Exception as e:
        print(f"❌ 错误：RawEvent 创建失败 - {e}")
        return False

    # 4. 测试 CollectorRegistry 可以正常工作
    try:
        registry = CollectorRegistry()
        print("✓ CollectorRegistry 可以正常实例化")
    except Exception as e:
        print(f"❌ 错误：CollectorRegistry 实例化失败 - {e}")
        return False

    # 5. 测试 collectors 包的导入
    try:
        from rayinfo_backend.collectors import registry

        print("✓ collectors 包仍然可以导入 registry")
    except Exception as e:
        print(f"❌ 错误：collectors 包导入失败 - {e}")
        return False

    print("\n🎉 BaseCollector 移除验证成功！")
    return True


def test_ray_scheduler_import():
    """测试 ray_scheduler 模块是否仍然可用"""

    print("\n=== 验证 RayScheduler 功能 ===")

    try:
        from rayinfo_backend.ray_scheduler import Task, BaseTaskConsumer, RayScheduler

        print("✓ RayScheduler 核心组件可以正常导入")
    except ImportError as e:
        print(f"❌ 错误：RayScheduler 导入失败 - {e}")
        return False

    # 测试 Task 创建
    try:
        task = Task(source="test", args={"test": "data"})
        print("✓ Task 可以正常创建")
    except Exception as e:
        print(f"❌ 错误：Task 创建失败 - {e}")
        return False

    print("✓ RayScheduler 功能验证成功")
    return True


def main():
    """运行所有测试"""
    print("开始验证 BaseCollector 移除操作...\n")

    success = True

    # 测试 BaseCollector 移除
    if not test_basecollector_removal():
        success = False

    # 测试 RayScheduler 功能
    if not test_ray_scheduler_import():
        success = False

    if success:
        print("\n✅ 所有验证测试通过！BaseCollector 已成功移除，其他功能正常。")
        return 0
    else:
        print("\n❌ 部分验证测试失败！")
        return 1


if __name__ == "__main__":
    sys.exit(main())
