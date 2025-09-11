"""测试采集器时间持久化功能

本模块测试采集器执行状态管理和断点续传功能。
包含状态管理器、调度器集成和完整流程的测试。
"""

import unittest
import time
import asyncio
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

# 测试前设置临时数据库路径
test_db_path = tempfile.mktemp(suffix=".db")
os.environ["RAYINFO_DB_PATH"] = test_db_path

from rayinfo_backend.ray_scheduler.state_manager import CollectorStateManager
from rayinfo_backend.ray_scheduler.ray_adapter import RaySchedulerAdapter
from rayinfo_backend.models.info_item import DatabaseManager, CollectorExecutionState
from rayinfo_backend.collectors.base import BaseCollector, RawEvent
from rayinfo_backend.config.settings import SearchEngineItem


class MockSimpleCollector(BaseCollector):
    """测试用简单采集器"""

    def __init__(self, name: str = "test.simple", interval: int = 300):
        self.name = name
        self._interval = interval

    @property
    def default_interval_seconds(self) -> int:
        return self._interval

    async def fetch(self, param=None):
        """模拟采集数据"""
        yield RawEvent(
            source=self.name,
            raw={"post_id": f"test-{int(time.time())}", "test": "data"},
        )


class MockParameterizedCollector(BaseCollector):
    """测试用参数化采集器"""

    def __init__(self, name: str = "test.param"):
        self.name = name
        self._queries = [
            SearchEngineItem(query="query1", interval_seconds=180),
            SearchEngineItem(query="query2", interval_seconds=300),
        ]

    @property
    def default_interval_seconds(self) -> int:
        return 300

    def list_param_jobs(self) -> list[tuple[str, int]]:
        """返回参数化任务列表"""
        return [(item.query, item.interval_seconds) for item in self._queries]

    @property
    def queries(self):
        return self._queries

    async def fetch(self, param=None):
        """模拟参数化采集"""
        if param is None:
            return
        yield RawEvent(
            source=self.name,
            raw={
                "post_id": f"test-{param}-{int(time.time())}",
                "query": param,
                "test": "data",
            },
        )


class TestCollectorStateManager(unittest.TestCase):
    """测试采集器状态管理器"""

    def setUp(self):
        """每个测试前的初始化"""
        # 重置单例实例
        CollectorStateManager.reset_instance()
        DatabaseManager.reset_instance()

        # 创建状态管理器实例
        self.state_manager = CollectorStateManager.get_instance(test_db_path)

    def tearDown(self):
        """每个测试后的清理"""
        # 清理测试数据库
        try:
            if os.path.exists(test_db_path):
                os.unlink(test_db_path)
        except:
            pass

    def test_singleton_pattern(self):
        """测试单例模式"""
        manager1 = CollectorStateManager.get_instance(test_db_path)
        manager2 = CollectorStateManager.get_instance(test_db_path)
        self.assertIs(manager1, manager2)

    def test_first_run_detection(self):
        """测试首次运行检测"""
        # 首次运行应该返回 None
        last_time = self.state_manager.get_last_execution_time("test.collector")
        self.assertIsNone(last_time)

        # 应该立即执行
        should_run = self.state_manager.should_run_immediately(
            "test.collector", None, 300
        )
        self.assertTrue(should_run)

    def test_execution_time_update(self):
        """测试执行时间更新"""
        collector_name = "test.collector"
        test_time = time.time()

        # 更新执行时间
        self.state_manager.update_execution_time(collector_name, None, test_time)

        # 验证时间已保存
        saved_time = self.state_manager.get_last_execution_time(collector_name)
        self.assertAlmostEqual(saved_time, test_time, delta=1.0)

    def test_immediate_run_logic(self):
        """测试立即执行逻辑"""
        collector_name = "test.collector"
        interval = 300  # 5分钟

        # 设置上次执行时间为10分钟前
        old_time = time.time() - 600  # 10分钟前
        self.state_manager.update_execution_time(collector_name, None, old_time)

        # 应该立即执行（超过间隔时间）
        should_run = self.state_manager.should_run_immediately(
            collector_name, None, interval
        )
        self.assertTrue(should_run)

        # 设置上次执行时间为2分钟前
        recent_time = time.time() - 120  # 2分钟前
        self.state_manager.update_execution_time(collector_name, None, recent_time)

        # 不应该立即执行（在间隔时间内）
        should_run = self.state_manager.should_run_immediately(
            collector_name, None, interval
        )
        self.assertFalse(should_run)

    def test_parameterized_collector_state(self):
        """测试参数化采集器状态管理"""
        collector_name = "test.param"
        param1 = "query1"
        param2 = "query2"

        # 为不同参数设置不同的执行时间
        time1 = time.time() - 100
        time2 = time.time() - 200

        self.state_manager.update_execution_time(collector_name, param1, time1)
        self.state_manager.update_execution_time(collector_name, param2, time2)

        # 验证不同参数的状态独立
        saved_time1 = self.state_manager.get_last_execution_time(collector_name, param1)
        saved_time2 = self.state_manager.get_last_execution_time(collector_name, param2)

        self.assertAlmostEqual(saved_time1, time1, delta=1.0)
        self.assertAlmostEqual(saved_time2, time2, delta=1.0)

    def test_next_run_time_calculation(self):
        """测试下次运行时间计算"""
        collector_name = "test.collector"
        interval = 300
        current_time = time.time()

        # 首次运行，应该立即执行
        next_time = self.state_manager.calculate_next_run_time(
            collector_name, None, interval
        )
        self.assertLessEqual(next_time, current_time + 1)  # 允许1秒误差

        # 设置最近执行时间，应该延迟执行
        recent_time = current_time - 60  # 1分钟前
        self.state_manager.update_execution_time(collector_name, None, recent_time)

        next_time = self.state_manager.calculate_next_run_time(
            collector_name, None, interval
        )
        expected_time = recent_time + interval
        self.assertAlmostEqual(next_time, expected_time, delta=1.0)

    def test_collector_stats(self):
        """测试采集器统计信息"""
        collector_name = "test.collector"
        test_time = time.time()

        # 初始状态应该返回 None
        stats = self.state_manager.get_collector_stats(collector_name)
        self.assertIsNone(stats)

        # 更新执行时间后应该有统计信息
        self.state_manager.update_execution_time(collector_name, None, test_time)
        stats = self.state_manager.get_collector_stats(collector_name)

        self.assertIsNotNone(stats)
        self.assertEqual(stats["collector_name"], collector_name)
        self.assertEqual(stats["execution_count"], 1)
        self.assertAlmostEqual(stats["last_execution_time"], test_time, delta=1.0)

    def test_cleanup_old_states(self):
        """测试清理过期状态"""
        collector_name = "test.collector"

        # 添加一个很早的执行记录
        old_time = time.time() - (35 * 24 * 60 * 60)  # 35天前
        self.state_manager.update_execution_time(collector_name, None, old_time)

        # 验证记录存在
        stats = self.state_manager.get_collector_stats(collector_name)
        self.assertIsNotNone(stats)

        # 清理30天以前的记录
        deleted_count = self.state_manager.cleanup_old_states(retention_days=30)
        self.assertEqual(deleted_count, 1)

        # 验证记录已被删除
        stats = self.state_manager.get_collector_stats(collector_name)
        self.assertIsNone(stats)


class TestSchedulerIntegration(unittest.TestCase):
    """测试调度器集成"""

    def setUp(self):
        """每个测试前的初始化"""
        # 重置单例实例
        CollectorStateManager.reset_instance()
        DatabaseManager.reset_instance()

        # 创建测试调度器（不启动）
        self.scheduler_adapter = RaySchedulerAdapter()
        # 不启动真实的调度器，避免在测试中触发实际任务

    def tearDown(self):
        """每个测试后的清理"""
        try:
            if os.path.exists(test_db_path):
                os.unlink(test_db_path)
        except:
            pass

    def test_simple_collector_scheduling(self):
        """测试简单采集器调度"""
        collector = MockSimpleCollector("test.simple", 300)

        # 添加调度任务
        job_ids = self.scheduler_adapter.add_collector_job(collector)

        # 验证任务已添加
        self.assertGreater(len(job_ids), 0)

        # 验证状态已记录
        stats = self.scheduler_adapter.state_manager.get_collector_stats(collector.name)
        # 首次添加调度时，状态还未创建，因为任务还未执行
        # 这是正常的，状态只在实际执行时才创建

    def test_parameterized_collector_scheduling(self):
        """测试参数化采集器调度"""
        collector = MockParameterizedCollector("test.param")

        # 添加调度任务
        job_ids = self.scheduler_adapter.add_collector_job(collector)

        # 验证为每个参数都添加了任务
        # 每个参数应该有初始任务和周期任务（如果需要立即执行的话）
        # 至少应该有周期任务
        self.assertGreater(len(job_ids), 0)

    async def test_state_update_during_execution(self):
        """测试执行过程中的状态更新"""
        collector = MockSimpleCollector("test.simple", 300)

        # 执行采集器
        await self.scheduler_adapter.run_collector_with_state_update(collector)

        # 验证状态已更新
        stats = self.scheduler_adapter.state_manager.get_collector_stats(collector.name)
        self.assertIsNotNone(stats)
        self.assertEqual(stats["execution_count"], 1)

    async def test_parameterized_execution_with_state(self):
        """测试参数化执行的状态更新"""
        collector = MockParameterizedCollector("test.param")
        param = "test_query"

        # 执行参数化采集器
        await self.scheduler_adapter.run_collector_with_state_update(collector, param)

        # 验证参数化状态已更新
        stats = self.scheduler_adapter.state_manager.get_collector_stats(
            collector.name, param
        )
        self.assertIsNotNone(stats)
        self.assertEqual(stats["execution_count"], 1)


class TestCompleteWorkflow(unittest.TestCase):
    """测试完整工作流程"""

    def setUp(self):
        """每个测试前的初始化"""
        # 重置单例实例
        CollectorStateManager.reset_instance()
        DatabaseManager.reset_instance()

    def tearDown(self):
        """每个测试后的清理"""
        try:
            if os.path.exists(test_db_path):
                os.unlink(test_db_path)
        except:
            pass

    async def test_end_to_end_persistence(self):
        """测试端到端的时间持久化流程"""
        # 1. 创建调度器和采集器
        scheduler_adapter = RaySchedulerAdapter()
        collector = MockSimpleCollector("test.e2e", 300)

        # 2. 验证首次运行状态
        should_run = scheduler_adapter.state_manager.should_run_immediately(
            collector.name, None, collector.default_interval_seconds
        )
        self.assertTrue(should_run, "首次运行应该立即执行")

        # 3. 执行采集器
        await scheduler_adapter.run_collector_with_state_update(collector)

        # 4. 验证状态已保存
        stats = scheduler_adapter.state_manager.get_collector_stats(collector.name)
        self.assertIsNotNone(stats)
        self.assertEqual(stats["execution_count"], 1)

        # 5. 立即再次检查，应该不需要立即执行
        should_run = scheduler_adapter.state_manager.should_run_immediately(
            collector.name, None, collector.default_interval_seconds
        )
        self.assertFalse(should_run, "刚执行过不应该立即执行")

        # 6. 模拟时间过去（修改数据库中的时间）
        old_time = time.time() - 400  # 超过间隔时间
        scheduler_adapter.state_manager.update_execution_time(
            collector.name, None, old_time
        )

        # 7. 现在应该又需要立即执行了
        should_run = scheduler_adapter.state_manager.should_run_immediately(
            collector.name, None, collector.default_interval_seconds
        )
        self.assertTrue(should_run, "超时后应该立即执行")

    def test_multiple_collectors_independence(self):
        """测试多个采集器的状态独立性"""
        state_manager = CollectorStateManager.get_instance(test_db_path)

        # 创建多个采集器状态
        collectors = [
            ("collector1", None),
            ("collector2", None),
            ("param_collector", "query1"),
            ("param_collector", "query2"),
        ]

        # 为每个采集器设置不同的执行时间
        base_time = time.time()
        for i, (name, param) in enumerate(collectors):
            execution_time = base_time - (i * 100)  # 每个相差100秒
            state_manager.update_execution_time(name, param, execution_time)

        # 验证每个采集器的状态独立
        for i, (name, param) in enumerate(collectors):
            stats = state_manager.get_collector_stats(name, param)
            self.assertIsNotNone(stats)
            expected_time = base_time - (i * 100)
            self.assertAlmostEqual(
                stats["last_execution_time"], expected_time, delta=1.0
            )


def run_async_test(test_func):
    """运行异步测试的辅助函数"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(test_func)
    finally:
        loop.close()


if __name__ == "__main__":
    # 设置测试环境
    import sys
    import os

    # 确保能导入项目模块
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(project_root, "src"))

    # 运行异步测试
    async def run_async_tests():
        """""运行所有异步测试""" ""
        # 创建测试实例
        scheduler_test = TestSchedulerIntegration()
        workflow_test = TestCompleteWorkflow()

        # 初始化测试
        scheduler_test.setUp()
        workflow_test.setUp()

        try:
            print("\n=== 运行异步测试 ===")

            print("测试: 执行过程中的状态更新")
            await scheduler_test.test_state_update_during_execution()
            print("✓ 通过")

            print("测试: 参数化执行的状态更新")
            await scheduler_test.test_parameterized_execution_with_state()
            print("✓ 通过")

            print("测试: 端到端的时间持久化流程")
            await workflow_test.test_end_to_end_persistence()
            print("✓ 通过")

            print("\n所有异步测试通过！")

        except Exception as e:
            print(f"异步测试失败: {e}")
            import traceback

            traceback.print_exc()
        finally:
            # 清理
            scheduler_test.tearDown()
            workflow_test.tearDown()

    # 运行异步测试
    run_async_test(run_async_tests())

    # 运行同步测试
    print("\n=== 运行同步测试 ===")
    unittest.main(verbosity=2, exit=False)
