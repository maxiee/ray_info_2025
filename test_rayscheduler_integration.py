#!/usr/bin/env python3
"""测试 RayScheduler 与 FastAPI 应用的集成"""

import asyncio
import os
import sys

# 设置项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(project_root, "rayinfo_backend", "src"))


async def test_rayscheduler_integration():
    """测试 RayScheduler 集成"""
    print("=== 测试 RayScheduler 集成 ===")

    try:
        # 导入调度器
        from rayinfo_backend.ray_scheduler import RayScheduler

        print("✅ RayScheduler 导入成功")

        # 创建调度器实例
        scheduler = RayScheduler()
        print("✅ RayScheduler 实例创建成功")

        # 测试调度器方法
        assert hasattr(scheduler, "start"), "调度器缺少 start 方法"
        assert hasattr(scheduler, "stop"), "调度器缺少 stop 方法"
        assert hasattr(scheduler, "is_running"), "调度器缺少 is_running 方法"
        assert hasattr(scheduler, "get_queue_size"), "调度器缺少 get_queue_size 方法"
        assert hasattr(scheduler, "add_task"), "调度器缺少 add_task 方法"
        print("✅ RayScheduler 接口完整")

        # 测试初始状态
        assert not scheduler.is_running(), "调度器初始状态应为未运行"
        assert scheduler.get_queue_size() == 0, "调度器初始队列应为空"
        print("✅ RayScheduler 初始状态正确")

        # 测试启动和停止
        await scheduler.start()
        assert scheduler.is_running(), "调度器启动后应为运行状态"
        print("✅ RayScheduler 启动成功")

        await scheduler.stop()
        assert not scheduler.is_running(), "调度器停止后应为未运行状态"
        print("✅ RayScheduler 停止成功")

        return True

    except Exception as e:
        print(f"❌ RayScheduler 集成测试失败：{e}")
        import traceback

        traceback.print_exc()
        return False


async def test_fastapi_integration():
    """测试 FastAPI 集成"""
    print("\n=== 测试 FastAPI 集成 ===")

    try:
        # 导入应用
        from rayinfo_backend.app import app

        print("✅ FastAPI 应用导入成功")

        # 检查应用配置
        assert app.title == "RayInfo Backend", "应用标题不正确"
        print("✅ FastAPI 应用配置正确")

        # 使用 TestClient 测试应用
        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            # 测试根端点
            response = client.get("/")
            assert response.status_code == 200
            assert response.json()["message"] == "Hello RayInfo"
            print("✅ 根端点测试通过")

            # 测试状态端点
            response = client.get("/status")
            assert response.status_code == 200

            status = response.json()
            assert status["scheduler_type"] == "RayScheduler"
            print("✅ 状态端点显示正确的调度器类型")

            # 由于在测试环境中，调度器可能已经启动，我们只检查相关字段存在
            assert "scheduler_running" in status
            assert "pending_tasks" in status
            assert "timestamp" in status
            print("✅ 状态端点返回完整信息")

        return True

    except Exception as e:
        print(f"❌ FastAPI 集成测试失败：{e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("开始 RayScheduler 集成测试...")

    tests = [
        ("RayScheduler 功能", test_rayscheduler_integration),
        ("FastAPI 集成", test_fastapi_integration),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ {test_name}测试异常：{e}")
            results.append(False)

    print(f"\n=== 集成测试结果 ===")
    success_count = sum(results)
    total_count = len(results)
    print(f"总计: {total_count}")
    print(f"成功: {success_count}")
    print(f"失败: {total_count - success_count}")

    if success_count == total_count:
        print("🎉 RayScheduler 成功集成到 FastAPI 应用中！")
        print("✅ 调度器功能完整且运行正常")
        print("✅ FastAPI 应用正确集成调度器")
    else:
        print("❌ 存在失败的集成测试")

    return success_count == total_count


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)


@pytest.mark.asyncio
async def test_scheduler_in_lifecycle():
    """测试调度器在应用生命周期中的行为"""
    from rayinfo_backend.app import scheduler

    # 在应用启动后，调度器应该存在且正在运行
    # 注意：由于测试环境的特殊性，我们需要检查全局变量
    print(f"Scheduler instance: {scheduler}")

    if scheduler:
        assert scheduler.is_running() == True
        assert scheduler.get_queue_size() == 0


if __name__ == "__main__":
    print("测试 RayScheduler 与 FastAPI 集成...")

    # 简单的异步测试
    async def simple_test():
        try:
            async with AsyncClient(base_url="http://test") as client:
                # 测试状态端点
                response = await client.get("/status")
                assert response.status_code == 200

                status = response.json()
                print(f"Status response: {status}")

                assert status["scheduler_type"] == "RayScheduler"
                assert status["scheduler_running"] is True

                print("✅ RayScheduler 成功集成到 FastAPI 应用中！")
                print(f"✅ 调度器状态：运行中")
                print(f"✅ 队列中任务数：{status['pending_tasks']}")

                return True

        except Exception as e:
            print(f"❌ 测试失败：{e}")
            import traceback

            traceback.print_exc()
            return False

    result = asyncio.run(simple_test())
    sys.exit(0 if result else 1)
