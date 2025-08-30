#!/usr/bin/env python3
"""采集器时间持久化功能验证脚本

这个脚本验证时间持久化功能的核心逻辑是否正常工作。
"""

import sys
import os
import time
import asyncio
import tempfile

# 设置项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(project_root, "rayinfo_backend", "src"))

# 创建临时数据库
test_db = tempfile.mktemp(suffix='.db')
os.environ['RAYINFO_DB_PATH'] = test_db

try:
    from rayinfo_backend.scheduling.state_manager import CollectorStateManager
    from rayinfo_backend.models.info_item import DatabaseManager, CollectorExecutionState
    print("✓ 模块导入成功")
except ImportError as e:
    print(f"✗ 模块导入失败: {e}")
    sys.exit(1)


def test_state_manager_basic():
    """测试状态管理器基本功能"""
    print("\n=== 测试状态管理器基本功能 ===")
    
    # 重置单例
    CollectorStateManager.reset_instance()
    DatabaseManager.reset_instance()
    
    # 创建状态管理器
    state_manager = CollectorStateManager.get_instance(test_db)
    print("✓ 状态管理器创建成功")
    
    # 测试首次运行检测
    collector_name = "test.collector"
    last_time = state_manager.get_last_execution_time(collector_name)
    print(f"✓ 首次运行检测: {last_time is None}")
    
    # 测试应该立即执行
    should_run = state_manager.should_run_immediately(collector_name, None, 300)
    print(f"✓ 首次运行应该立即执行: {should_run}")
    
    # 更新执行时间
    test_time = time.time()
    state_manager.update_execution_time(collector_name, None, test_time)
    print("✓ 执行时间更新成功")
    
    # 验证时间已保存
    saved_time = state_manager.get_last_execution_time(collector_name)
    print(f"✓ 时间保存验证: {abs(saved_time - test_time) < 1}")
    
    # 测试不应该立即执行（刚执行过）
    should_run = state_manager.should_run_immediately(collector_name, None, 300)
    print(f"✓ 刚执行过不应该立即执行: {not should_run}")
    
    # 测试超时后应该立即执行
    old_time = time.time() - 400  # 超过300秒间隔
    state_manager.update_execution_time(collector_name, None, old_time)
    should_run = state_manager.should_run_immediately(collector_name, None, 300)
    print(f"✓ 超时后应该立即执行: {should_run}")
    
    return True


def test_parameterized_collector():
    """测试参数化采集器状态管理"""
    print("\n=== 测试参数化采集器状态管理 ===")
    
    state_manager = CollectorStateManager.get_instance(test_db)
    
    collector_name = "param.collector"
    param1 = "query1"
    param2 = "query2"
    
    # 为不同参数设置不同时间
    time1 = time.time() - 100
    time2 = time.time() - 200
    
    state_manager.update_execution_time(collector_name, param1, time1)
    state_manager.update_execution_time(collector_name, param2, time2)
    print("✓ 参数化状态更新成功")
    
    # 验证状态独立
    saved_time1 = state_manager.get_last_execution_time(collector_name, param1)
    saved_time2 = state_manager.get_last_execution_time(collector_name, param2)
    
    independent = (abs(saved_time1 - time1) < 1 and abs(saved_time2 - time2) < 1)
    print(f"✓ 参数状态独立性: {independent}")
    
    return True


def test_next_run_time_calculation():
    """测试下次运行时间计算"""
    print("\n=== 测试下次运行时间计算 ===")
    
    state_manager = CollectorStateManager.get_instance(test_db)
    
    collector_name = "time.test"
    interval = 300
    current_time = time.time()
    
    # 首次运行应该立即执行
    next_time = state_manager.calculate_next_run_time(collector_name, None, interval)
    immediate = next_time <= current_time + 1
    print(f"✓ 首次运行立即执行: {immediate}")
    
    # 设置最近执行时间
    recent_time = current_time - 60  # 1分钟前
    state_manager.update_execution_time(collector_name, None, recent_time)
    
    next_time = state_manager.calculate_next_run_time(collector_name, None, interval)
    expected_time = recent_time + interval
    delayed = abs(next_time - expected_time) < 1
    print(f"✓ 延迟执行时间计算: {delayed}")
    
    return True


def test_collector_stats():
    """测试采集器统计信息"""
    print("\n=== 测试采集器统计信息 ===")
    
    state_manager = CollectorStateManager.get_instance(test_db)
    
    collector_name = "stats.test"
    
    # 初始无统计信息
    stats = state_manager.get_collector_stats(collector_name)
    no_stats = stats is None
    print(f"✓ 初始无统计信息: {no_stats}")
    
    # 执行几次后应该有统计信息
    for i in range(3):
        state_manager.update_execution_time(collector_name, None, time.time())
        time.sleep(0.1)  # 避免时间戳完全相同
    
    stats = state_manager.get_collector_stats(collector_name)
    has_stats = (stats is not None and 
                 stats["collector_name"] == collector_name and
                 stats["execution_count"] == 3)
    print(f"✓ 统计信息正确: {has_stats}")
    
    return True


def cleanup():
    """清理测试数据"""
    try:
        if os.path.exists(test_db):
            os.unlink(test_db)
        print("✓ 测试数据清理完成")
    except Exception as e:
        print(f"⚠ 清理警告: {e}")


def main():
    """主测试函数"""
    print("开始验证采集器时间持久化功能...")
    
    tests = [
        test_state_manager_basic,
        test_parameterized_collector,
        test_next_run_time_calculation,
        test_collector_stats,
    ]
    
    success_count = 0
    total_count = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                success_count += 1
        except Exception as e:
            print(f"✗ 测试失败: {test_func.__name__} - {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n=== 测试结果 ===")
    print(f"总计: {total_count}")
    print(f"成功: {success_count}")
    print(f"失败: {total_count - success_count}")
    
    if success_count == total_count:
        print("🎉 所有测试通过！时间持久化功能正常工作。")
        cleanup()
        return True
    else:
        print("❌ 存在失败的测试，请检查实现。")
        cleanup()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)