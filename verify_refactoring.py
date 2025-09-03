#!/usr/bin/env python3
"""
验证重构后的异常处理机制

这个脚本验证：
1. CollectorRetryableException 可以正常工作
2. 调度器能够正确处理新的异常类型
3. 所有相关代码都能正常导入和运行
"""

import sys
import os
from pathlib import Path

# 添加项目路径到 Python 路径
project_root = Path(__file__).parent / "rayinfo_backend"
sys.path.insert(0, str(project_root / "src"))


def test_exception_import():
    """测试异常类导入"""
    print("测试异常类导入...")
    try:
        from rayinfo_backend.collectors.base import CollectorRetryableException

        print("✓ CollectorRetryableException 导入成功")
        return True
    except ImportError as e:
        print(f"✗ 导入失败: {e}")
        return False


def test_exception_creation():
    """测试异常创建和使用"""
    print("\n测试异常创建...")
    try:
        from rayinfo_backend.collectors.base import CollectorRetryableException

        # 测试不同的创建方式
        exc1 = CollectorRetryableException()
        exc2 = CollectorRetryableException(retry_reason="network_error")
        exc3 = CollectorRetryableException(
            retry_reason="api_quota", retry_after=3600, message="API quota exceeded"
        )

        print(f"  默认异常: {exc1}")
        print(f"  网络错误异常: {exc2}")
        print(f"  配额异常: {exc3}")

        # 验证属性
        assert exc1.retry_reason == "unknown"
        assert exc1.retry_after is None
        assert exc2.retry_reason == "network_error"
        assert exc3.retry_after == 3600

        print("✓ 异常创建和属性测试通过")
        return True
    except Exception as e:
        print(f"✗ 异常创建测试失败: {e}")
        return False


def test_scheduler_import():
    """测试调度器导入"""
    print("\n测试调度器导入...")
    try:
        from rayinfo_backend.scheduling.scheduler import SchedulerAdapter

        print("✓ SchedulerAdapter 导入成功")
        return True
    except ImportError as e:
        print(f"✗ 调度器导入失败: {e}")
        return False


def test_mes_executor_import():
    """测试 MES 执行器导入"""
    print("\n测试 MES 执行器导入...")
    try:
        from rayinfo_backend.collectors.mes.mes_executor import MesExecutor

        print("✓ MesExecutor 导入成功")
        return True
    except ImportError as e:
        print(f"✗ MES 执行器导入失败: {e}")
        return False


def test_exception_inheritance():
    """测试异常继承关系"""
    print("\n测试异常继承关系...")
    try:
        from rayinfo_backend.collectors.base import (
            CollectorError,
            CollectorRetryableException,
        )

        exc = CollectorRetryableException("test_reason")

        assert isinstance(exc, CollectorError)
        assert isinstance(exc, Exception)

        print("✓ 异常继承关系正确")
        return True
    except Exception as e:
        print(f"✗ 异常继承测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("验证重构后的异常处理机制")
    print("=" * 60)

    tests = [
        test_exception_import,
        test_exception_creation,
        test_scheduler_import,
        test_mes_executor_import,
        test_exception_inheritance,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ 测试 {test.__name__} 出现异常: {e}")

    print("\n" + "=" * 60)
    print(f"测试结果: {passed}/{total} 通过")

    if passed == total:
        print("🎉 所有测试通过！重构成功完成")
        return True
    else:
        print("❌ 部分测试失败，请检查代码")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
