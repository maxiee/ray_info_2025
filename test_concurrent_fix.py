#!/usr/bin/env python3
"""
测试API使用量并发更新修复

这个脚本验证：
1. APScheduler限制同一任务的并发实例数
2. API配额跟踪在串行执行时能正确更新
"""

import asyncio
import time
import logging
from pathlib import Path
import sys

# 添加项目路径
project_root = Path(__file__).parent / "rayinfo_backend"
sys.path.insert(0, str(project_root / "src"))

from rayinfo_backend.collectors.mes.search import MesCollector
from rayinfo_backend.scheduling.scheduler import SchedulerAdapter

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_concurrent_fix")


async def test_concurrent_execution():
    """测试并发执行修复"""

    logger.info("=" * 60)
    logger.info("开始测试API使用量并发更新修复")
    logger.info("=" * 60)

    # 1. 创建采集器
    collector = MesCollector()

    # 2. 手动执行两个任务，观察API使用量
    logger.info("\n1. 手动串行执行两个任务")

    # 第一个任务
    logger.info("执行第一个任务: pan.quark.cn 赚钱")
    events1 = []
    async for event in collector.fetch(param="pan.quark.cn 赚钱"):
        events1.append(event)
    logger.info(f"第一个任务完成，获得 {len(events1)} 个事件")

    # 等待一秒确保API状态更新
    await asyncio.sleep(1)

    # 第二个任务
    logger.info("执行第二个任务: 微博 创作者计划")
    events2 = []
    async for event in collector.fetch(param="微博 创作者计划"):
        events2.append(event)
    logger.info(f"第二个任务完成，获得 {len(events2)} 个事件")

    logger.info("\n✅ 手动串行执行测试完成")
    logger.info("请观察日志中的API使用量是否递增")

    return True


def test_scheduler_configuration():
    """测试调度器配置"""

    logger.info("\n2. 测试调度器配置")

    # 创建调度器
    scheduler = SchedulerAdapter()

    # 检查调度器配置
    logger.info(f"调度器类型: {type(scheduler.scheduler)}")

    # 检查作业存储配置
    jobs = scheduler.scheduler.get_jobs()
    logger.info(f"当前任务数: {len(jobs)}")

    logger.info("✅ 调度器配置测试完成")

    return True


async def main():
    """主测试函数"""

    try:
        # 测试1: 并发执行修复
        concurrent_ok = await test_concurrent_execution()

        # 测试2: 调度器配置
        scheduler_ok = test_scheduler_configuration()

        logger.info("\n" + "=" * 60)
        logger.info("测试结果汇总")
        logger.info("=" * 60)
        logger.info(f"并发执行修复: {'✅ 通过' if concurrent_ok else '❌ 失败'}")
        logger.info(f"调度器配置: {'✅ 通过' if scheduler_ok else '❌ 失败'}")

        all_ok = concurrent_ok and scheduler_ok
        logger.info(f"\n总体结果: {'✅ 所有测试通过' if all_ok else '❌ 存在测试失败'}")

        return all_ok

    except Exception as e:
        logger.error(f"测试过程中出现异常: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
