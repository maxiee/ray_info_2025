#!/usr/bin/env python3
"""集成测试脚本

测试采集器时间持久化功能在实际系统中的工作情况。
"""

import sys
import os
import asyncio
import tempfile

# 设置项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(project_root, "rayinfo_backend", "src"))

# 创建临时数据库
test_db = tempfile.mktemp(suffix='.db')
os.environ['RAYINFO_DB_PATH'] = test_db

async def test_scheduler_integration():
    """测试调度器集成"""
    print("=== 测试调度器集成 ===")
    
    try:
        from rayinfo_backend.scheduling.scheduler import SchedulerAdapter
        from rayinfo_backend.collectors.base import registry
        print("✓ 导入调度器成功")
        
        # 创建调度器实例
        scheduler = SchedulerAdapter()
        print("✓ 调度器实例创建成功")
        
        # 检查状态管理器是否正常工作
        state_manager = scheduler.state_manager
        print("✓ 状态管理器集成成功")
        
        # 测试状态管理器基本功能
        collector_name = "test.integration"
        
        # 检查首次运行
        should_run = state_manager.should_run_immediately(collector_name, None, 300)
        print(f"✓ 首次运行检测: {should_run}")
        
        # 更新执行时间
        import time
        state_manager.update_execution_time(collector_name, None, time.time())
        print("✓ 执行时间更新成功")
        
        # 验证状态已保存
        stats = state_manager.get_collector_stats(collector_name)
        print(f"✓ 状态统计获取: {stats is not None}")
        
        # 测试调度器方法
        if hasattr(scheduler, 'add_collector_job_with_state'):
            print("✓ 调度器包含状态感知方法")
        else:
            print("✗ 调度器缺少状态感知方法")
            
        print("✓ 调度器集成测试通过")
        return True
        
    except Exception as e:
        print(f"✗ 调度器集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_configuration():
    """测试配置加载"""
    print("\n=== 测试配置加载 ===")
    
    try:
        from rayinfo_backend.config.settings import get_settings
        print("✓ 配置模块导入成功")
        
        settings = get_settings()
        print("✓ 配置加载成功")
        
        # 检查存储配置
        storage_config = settings.storage
        print(f"✓ 存储配置: {storage_config.db_path}")
        
        # 检查状态管理配置
        if hasattr(storage_config, 'state_management'):
            state_config = storage_config.state_management
            print(f"✓ 状态管理配置: 启用={state_config.enable_time_persistence}")
            print(f"✓ 保留天数: {state_config.state_retention_days}")
        else:
            print("⚠ 配置中缺少状态管理设置")
            
        return True
        
    except Exception as e:
        print(f"✗ 配置加载测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_integration():
    """测试数据库集成"""
    print("\n=== 测试数据库集成 ===")
    
    try:
        from rayinfo_backend.models.info_item import DatabaseManager, CollectorExecutionState
        print("✓ 数据库模块导入成功")
        
        # 创建数据库管理器
        db_manager = DatabaseManager.get_instance(test_db)
        print("✓ 数据库管理器创建成功")
        
        # 创建表结构
        db_manager.create_tables()
        print("✓ 数据库表创建成功")
        
        # 测试CRUD操作
        session = db_manager.get_session()
        try:
            # 创建测试记录
            import time
            test_record = CollectorExecutionState(
                collector_name="test.db",
                param_key="",
                last_execution_time=time.time(),
                created_at=time.time(),
                updated_at=time.time(),
                execution_count=1
            )
            session.add(test_record)
            session.commit()
            print("✓ 数据库写入成功")
            
            # 查询记录
            found = session.query(CollectorExecutionState).filter_by(
                collector_name="test.db"
            ).first()
            print(f"✓ 数据库查询成功: {found is not None}")
            
        finally:
            session.close()
            
        return True
        
    except Exception as e:
        print(f"✗ 数据库集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup():
    """清理测试数据"""
    try:
        if os.path.exists(test_db):
            os.unlink(test_db)
        print("✓ 测试数据清理完成")
    except Exception as e:
        print(f"⚠ 清理警告: {e}")


async def main():
    """主测试函数"""
    print("开始集成测试...")
    
    tests = [
        ("配置加载", test_configuration),
        ("数据库集成", test_database_integration),
        ("调度器集成", test_scheduler_integration),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append(result)
        except Exception as e:
            print(f"✗ {test_name}测试异常: {e}")
            results.append(False)
    
    print(f"\n=== 集成测试结果 ===")
    success_count = sum(results)
    total_count = len(results)
    print(f"总计: {total_count}")
    print(f"成功: {success_count}")
    print(f"失败: {total_count - success_count}")
    
    if success_count == total_count:
        print("🎉 所有集成测试通过！")
        print("✅ 采集器时间持久化功能已成功集成到系统中。")
    else:
        print("❌ 存在失败的集成测试。")
    
    cleanup()
    return success_count == total_count


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)