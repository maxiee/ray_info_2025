#!/usr/bin/env python3
"""
测试 Google API 限额处理逻辑

这个脚本用于验证：
1. MesCollector 能正确检测并抛出 QuotaExceededException
2. 调度器能正确处理限额异常，不更新状态并重调度到24小时后
3. 持久化记录保持在上次成功执行的时间点
"""

import asyncio
import json
import time
import logging
import sys
import os
from pathlib import Path

# 添加项目路径到 Python 路径
project_root = Path(__file__).parent / "rayinfo_backend"
sys.path.insert(0, str(project_root / "src"))

# 导入必要的模块
from rayinfo_backend.collectors.mes.search import MesCollector
from rayinfo_backend.collectors.base import QuotaExceededException
from rayinfo_backend.scheduling.scheduler import SchedulerAdapter
from rayinfo_backend.scheduling.state_manager import CollectorStateManager
from rayinfo_backend.config.settings import get_settings

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_quota")


def create_mock_mes_output_quota_exceeded():
    """创建模拟的 mes 输出，表示 Google API 配额已超限"""
    return {
        "results": [
            {
                "title": "Test Result",
                "url": "https://example.com/test",
                "description": "Test description",
                "engine": "google",  # 确保引擎是 google
            }
        ],
        "count": 1,
        "rate_limit": {
            "requests_used": 100,
            "daily_limit": 100,
            "requests_remaining": 0,
            "limit_exceeded": True,
        },
    }


def create_mock_mes_output_normal():
    """创建模拟的 mes 输出，表示正常执行"""
    return {
        "results": [
            {
                "title": "Normal Result",
                "url": "https://example.com/normal",
                "description": "Normal description",
                "engine": "google",
            }
        ],
        "count": 1,
        "rate_limit": {
            "requests_used": 50,
            "daily_limit": 100,
            "requests_remaining": 50,
            "limit_exceeded": False,
        },
    }


class MockMesCollector(MesCollector):
    """用于测试的模拟 MesCollector"""

    def __init__(self, simulate_quota_exceeded=False):
        super().__init__()
        self.simulate_quota_exceeded = simulate_quota_exceeded

    def _choose_engine(self, query: str) -> str:
        """在测试中固定返回 google 引擎"""
        if self.simulate_quota_exceeded:
            return "google"  # 配额测试使用 Google
        return "duckduckgo"  # 正常测试使用 DuckDuckGo

    async def _run_mes(self, query: str, engine: str, time_range=None):
        """模拟 mes 命令执行"""
        logger.info(f"模拟执行 mes 命令: query={query}, engine={engine}")

        if self.simulate_quota_exceeded:
            # 模拟配额超限
            mock_output = create_mock_mes_output_quota_exceeded()
            logger.info("模拟 Google API 配额超限场景")
        else:
            # 模拟正常执行
            mock_output = create_mock_mes_output_normal()
            logger.info("模拟正常执行场景")

        # 模拟与实际实现相同的逻辑
        if isinstance(mock_output, dict) and "results" in mock_output:
            results = mock_output["results"]
            if "rate_limit" in mock_output:
                rate_limit = mock_output["rate_limit"]
                limit_exceeded = rate_limit.get("limit_exceeded", False)
                requests_used = rate_limit.get("requests_used", 0)
                daily_limit = rate_limit.get("daily_limit", 0)

                logger.info(
                    "Search API rate limit info - used: %s/%s, remaining: %s, limit_exceeded: %s",
                    requests_used,
                    daily_limit,
                    rate_limit.get("requests_remaining", 0),
                    limit_exceeded,
                )

                # 检查是否达到 Google API 限额
                if limit_exceeded and engine.lower() == "google":
                    reset_time = time.time() + 24 * 3600  # 24小时后

                    logger.warning(
                        "Google API daily quota exceeded - used: %s/%s, engine: %s",
                        requests_used,
                        daily_limit,
                        engine,
                    )

                    # 抛出配额超限异常
                    raise QuotaExceededException(
                        api_type="google",
                        reset_time=reset_time,
                        message=f"Google Search API daily quota exceeded (used {requests_used}/{daily_limit})",
                    )

            return results
        else:
            return []


async def test_quota_exception_handling():
    """测试配额异常处理的完整流程"""

    logger.info("=" * 60)
    logger.info("开始测试 Google API 配额异常处理")
    logger.info("=" * 60)

    # 1. 测试正常执行情况（确保基础功能正常）
    logger.info("\n1. 测试正常执行情况")
    normal_collector = MockMesCollector(simulate_quota_exceeded=False)

    try:
        events = []
        async for event in normal_collector.fetch(param="test query"):
            events.append(event)
        logger.info(f"正常执行成功，获得 {len(events)} 个事件")
    except Exception as e:
        logger.error(f"正常执行失败：{e}")
        return False

    # 2. 测试配额超限情况
    logger.info("\n2. 测试配额超限情况")
    quota_collector = MockMesCollector(simulate_quota_exceeded=True)

    try:
        events = []
        async for event in quota_collector.fetch(param="test query"):
            events.append(event)
        logger.error("预期应该抛出 QuotaExceededException，但没有抛出")
        return False
    except QuotaExceededException as e:
        logger.info(f"成功捕获配额超限异常：{e}")
        logger.info(f"API类型：{e.api_type}")
        logger.info(f"重置时间：{e.reset_time}")
        logger.info(f"异常消息：{e}")
    except Exception as e:
        logger.error(f"捕获了意外的异常类型：{type(e).__name__}: {e}")
        return False

    logger.info("\n✅ 配额异常处理测试通过")
    return True


async def test_scheduler_integration():
    """测试调度器与配额异常的集成"""

    logger.info("\n" + "=" * 60)
    logger.info("开始测试调度器集成")
    logger.info("=" * 60)

    # 创建一个临时的状态管理器用于测试
    test_db_path = "/tmp/test_quota_rayinfo.db"
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    state_manager = CollectorStateManager.get_instance(test_db_path)

    # 记录初始状态
    collector_name = "mes.search"
    param_key = "test query"

    initial_last_time = state_manager.get_last_execution_time(collector_name, param_key)
    logger.info(f"初始执行状态：{initial_last_time}")

    # 模拟正常执行并更新状态
    success_time = time.time()
    state_manager.update_execution_time(collector_name, param_key, success_time)

    after_success_time = state_manager.get_last_execution_time(
        collector_name, param_key
    )
    logger.info(f"正常执行后状态：{after_success_time}")

    # 创建调度器（但不启动）
    scheduler = SchedulerAdapter()

    # 模拟配额超限的执行
    quota_collector = MockMesCollector(simulate_quota_exceeded=True)
    quota_collector.name = collector_name

    try:
        # 调度器应该会处理配额异常并不更新状态
        await scheduler.run_collector_with_state_update(quota_collector, param_key)
        # 如果没有异常，说明调度器正确处理了配额异常
        logger.info("调度器正确处理了配额异常，没有抛出异常")
    except Exception as e:
        # 如果有异常，说明调度器处理不正确
        logger.error(f"调度器处理配额异常时出现意外异常：{type(e).__name__}: {e}")
        return False

    # 检查状态是否保持不变
    after_quota_fail_time = state_manager.get_last_execution_time(
        collector_name, param_key
    )
    logger.info(f"配额失败后状态：{after_quota_fail_time}")

    if after_quota_fail_time == after_success_time:
        logger.info("✅ 状态保持不变，配额失败不更新执行时间")
        return True
    else:
        logger.error("❌ 状态发生了变化，这不符合预期")
        return False


def test_configuration():
    """测试配置是否正确加载"""

    logger.info("\n" + "=" * 60)
    logger.info("开始测试配置加载")
    logger.info("=" * 60)

    try:
        collector = MesCollector()
        logger.info(f"采集器名称：{collector.name}")
        logger.info(f"查询任务数量：{len(collector._query_jobs)}")

        for query, interval, engine, time_range in collector._query_jobs:
            logger.info(
                f"查询配置：query={query}, interval={interval}, engine={engine}, time_range={time_range}"
            )

        logger.info("✅ 配置加载测试通过")
        return True
    except Exception as e:
        logger.error(f"❌ 配置加载失败：{e}")
        return False


async def main():
    """主测试函数"""

    logger.info("Google API 配额处理逻辑测试开始")

    # 测试配置加载
    config_ok = test_configuration()

    # 测试配额异常处理
    quota_ok = await test_quota_exception_handling()

    # 测试调度器集成
    scheduler_ok = await test_scheduler_integration()

    logger.info("\n" + "=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)
    logger.info(f"配置加载：{'✅ 通过' if config_ok else '❌ 失败'}")
    logger.info(f"配额异常处理：{'✅ 通过' if quota_ok else '❌ 失败'}")
    logger.info(f"调度器集成：{'✅ 通过' if scheduler_ok else '❌ 失败'}")

    all_ok = config_ok and quota_ok and scheduler_ok
    logger.info(f"\n总体结果：{'✅ 所有测试通过' if all_ok else '❌ 存在测试失败'}")

    return all_ok


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
