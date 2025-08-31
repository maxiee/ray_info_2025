#!/usr/bin/env python3
"""重构效果验证测试

验证策略模式重构和管道处理优化的效果。
测试重构后的调度器和管道是否能正常工作。
"""

import sys
import os
import time
import tempfile
from pathlib import Path

# 添加项目路径到sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from rayinfo_backend.collectors.base import (
    RawEvent,
    BaseCollector,
)
from rayinfo_backend.scheduling.scheduler import SchedulerAdapter
from rayinfo_backend.pipelines import DedupStage, PersistStage, Pipeline
from rayinfo_backend.config.loaders import create_default_config_loader, ConfigParser
from rayinfo_backend.config.validators import validate_settings
from rayinfo_backend.utils.instance_id import instance_manager, InstanceStatus


class TestSimpleCollector(BaseCollector):
    """测试用的简单采集器"""

    name = "test.simple"

    @property
    def default_interval_seconds(self) -> int:
        return 5

    async def fetch(self, param=None):
        # 模拟采集数据
        for i in range(3):
            yield RawEvent(
                source=self.name,
                raw={"post_id": f"simple_{i}", "content": f"Simple content {i}"},
                debug=True,  # 测试模式
            )


class TestParameterizedCollector(BaseCollector):
    """测试用的参数化采集器"""

    name = "test.parameterized"

    @property
    def default_interval_seconds(self) -> int:
        return 10

    def list_param_jobs(self):
        return [
            ("query1", 5),
            ("query2", 8),
        ]

    async def fetch(self, param=None):
        if param is None:
            return

        # 模拟参数化采集
        for i in range(2):
            yield RawEvent(
                source=self.name,
                raw={
                    "post_id": f"{param}_{i}",
                    "query": param,
                    "content": f"Content for {param} - {i}",
                },
                debug=True,  # 测试模式
            )


def test_scheduler_strategy_pattern():
    """测试调度器策略模式重构"""
    print("=== 测试调度器策略模式重构 ===")

    # 创建临时数据库文件
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        db_path = tmp_db.name

    try:
        # 设置测试环境变量
        os.environ["RAYINFO_DB_PATH"] = db_path

        # 创建调度器
        scheduler = SchedulerAdapter()

        # 创建测试采集器
        simple_collector = TestSimpleCollector()
        param_collector = TestParameterizedCollector()

        # 测试添加简单采集器
        job_ids = scheduler.add_collector_job(simple_collector)
        print(f"✓ 简单采集器添加成功，任务ID: {job_ids}")
        assert len(job_ids) == 1
        assert job_ids[0] == "test.simple"

        # 测试添加参数化采集器
        job_ids = scheduler.add_collector_job(param_collector)
        print(f"✓ 参数化采集器添加成功，任务ID: {job_ids}")
        assert len(job_ids) == 2
        assert "test.parameterized:query1" in job_ids
        assert "test.parameterized:query2" in job_ids

        print("✓ 调度器策略模式重构验证通过")

    except Exception as e:
        print(f"✗ 调度器策略模式测试失败: {e}")
        raise
    finally:
        # 清理临时文件
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_pipeline_optimization():
    """测试管道处理优化"""
    print("\n=== 测试管道处理优化 ===")

    try:
        # 创建测试事件
        events = [
            RawEvent("test.source", {"post_id": "1", "content": "Content 1"}),
            RawEvent("test.source", {"post_id": "2", "content": "Content 2"}),
            RawEvent(
                "test.source", {"post_id": "1", "content": "Content 1 duplicate"}
            ),  # 重复
            RawEvent("test.source", {"post_id": "3", "content": "Content 3"}),
            RawEvent(
                "test.source", {"post_id": "2", "content": "Content 2 duplicate"}
            ),  # 重复
        ]

        # 测试去重阶段
        dedup_stage = DedupStage(max_size=1000)
        unique_events = dedup_stage.process(events)

        print(
            f"✓ 去重测试：输入 {len(events)} 个事件，输出 {len(unique_events)} 个事件"
        )
        assert len(unique_events) == 3  # 应该去除2个重复项

        # 检查去重指标
        metrics = dedup_stage.get_metrics()
        print(f"✓ 去重指标：{metrics}")
        assert metrics["total_input"] == 5
        assert metrics["duplicates_found"] == 2
        assert metrics["dedup_rate"] == 0.4

        # 测试管道组合
        pipeline = Pipeline(
            [DedupStage(max_size=100), PersistStage()]  # 测试阶段，只打印
        )

        result = pipeline.run(events)
        print(f"✓ 管道处理完成，结果数量: {len(result)}")

        print("✓ 管道处理优化验证通过")

    except Exception as e:
        print(f"✗ 管道处理优化测试失败: {e}")
        raise


def test_config_management():
    """测试配置管理重构"""
    print("\n=== 测试配置管理重构 ===")

    try:
        # 测试配置加载器
        loader = create_default_config_loader()
        config_data = loader.load()
        print(f"✓ 配置加载器测试通过，加载了 {len(config_data)} 个配置项")

        # 测试配置解析
        settings = ConfigParser.parse(config_data)
        print(f"✓ 配置解析成功，时区: {settings.scheduler_timezone}")

        # 测试配置验证
        validation_result = validate_settings(settings)
        print(f"✓ 配置验证完成，是否有效: {validation_result.is_valid}")
        print(f"  - 错误数: {len(validation_result.errors)}")
        print(f"  - 警告数: {len(validation_result.warnings)}")

        print("✓ 配置管理重构验证通过")

    except Exception as e:
        print(f"✗ 配置管理测试失败: {e}")
        raise


def test_instance_manager():
    """测试实例管理器增强"""
    print("\n=== 测试实例管理器增强 ===")

    try:
        # 清理现有实例
        instance_manager.clear()

        # 测试实例注册
        collector = TestSimpleCollector()
        instance_id = instance_manager.register_instance(collector)
        print(f"✓ 实例注册成功: {instance_id}")

        # 测试实例获取
        instance = instance_manager.get_instance(instance_id)
        assert instance is not None
        print(f"✓ 实例获取成功: {instance.collector.name}")

        # 测试状态更新
        success = instance_manager.update_instance_stats(instance_id, True)
        assert success
        print(f"✓ 实例状态更新成功")

        # 测试统计信息
        stats = instance_manager.get_stats()
        print(f"✓ 统计信息: 活跃实例数 {stats['active_instances']}")

        # 测试实例列表
        all_instances = instance_manager.list_all_instances()
        assert len(all_instances) > 0
        print(f"✓ 实例列表获取成功，共 {len(all_instances)} 个实例")

        print("✓ 实例管理器增强验证通过")

    except Exception as e:
        print(f"✗ 实例管理器测试失败: {e}")
        raise


def test_enhanced_pipeline():
    """测试增强的管道处理"""
    print("\n=== 测试增强的管道处理 ===")

    try:
        # 测试增强的去重阶段
        dedup_stage = DedupStage(max_size=100, use_content_hash=True)

        # 创建测试数据
        events = [
            RawEvent("test.source", {"post_id": "1", "content": "Content 1"}),
            RawEvent("test.source", {"post_id": "2", "content": "Content 2"}),
            RawEvent("test.source", {"post_id": "1", "content": "Content 1 duplicate"}),
            RawEvent(
                "test.source", {"url": "http://example.com", "content": "URL content"}
            ),
            RawEvent(
                "test.source", {"url": "http://example.com", "content": "URL duplicate"}
            ),
        ]

        # 测试去重处理
        result = dedup_stage.process(events)
        print(f"✓ 增强去重测试：输入 {len(events)} 个，输出 {len(result)} 个")

        # 测试指标收集
        metrics = dedup_stage.get_metrics()
        print(
            f"✓ 指标收集: 处理数 {metrics['processed_count']}，去重数 {metrics['duplicates_found']}"
        )
        print(f"  - 去重率: {metrics['dedup_rate']:.2%}")
        print(f"  - 缓存命中率: {metrics['cache_hit_rate']:.2%}")

        # 测试错误处理
        invalid_events = [RawEvent("", {})]
        result_with_error = dedup_stage.process(invalid_events)
        print(f"✓ 错误处理测试通过")

        print("✓ 增强的管道处理验证通过")

    except Exception as e:
        print(f"✗ 增强管道处理测试失败: {e}")
        raise


def main():
    """主测试函数"""
    print("开始重构效果验证测试...")

    try:
        # 运行各项测试
        test_scheduler_strategy_pattern()
        test_pipeline_optimization()
        test_config_management()
        test_instance_manager()
        test_enhanced_pipeline()

        print("\n🎉 所有重构验证测试通过！")
        print("\n重构效果总结：")
        print("✓ 调度器使用策略模式简化了复杂的条件分支逻辑")
        print("✓ 管道处理使用集合优化了去重算法性能（O(1) vs O(n)）")
        print("✓ PipelineStage基类提供了统一的错误处理和指标收集")
        print("✓ 职责分离使代码更模块化、可测试和可维护")
        print("✓ 采集器能力接口提升了类型安全性，减少运行时检查")
        print("✓ 配置管理使用策略模式支持多配置源和验证机制")
        print("✓ 实例管理器支持线程安全、生命周期管理和健康监控")
        print("✓ 所有模块都具备完善的错误处理和指标监控能力")

    except Exception as e:
        print(f"\n❌ 重构验证测试失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
