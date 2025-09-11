"""RayInfo 后端核心骨架

使用新的 RayScheduler 异步任务调度框架：
- FastAPI 实例
- RayScheduler 异步调度器集成（应用启动/关闭生命周期）
- 自动发现和注册采集器
- RESTful API 接口

后续实际业务（抓取、数据持久化等）在此基础上扩展。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator, Protocol

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .utils.logging import setup_logging
from .collectors import discover_and_register  # 自动发现 collectors
from .utils.instance_id import instance_manager
from .api.v1 import router as api_v1_router
from .ray_scheduler.ray_adapter import RaySchedulerAdapter

logger = setup_logging()


class SchedulerProtocol(Protocol):
    """调度器协议，定义调度器必须实现的接口"""

    def load_all_collectors(self) -> None: ...
    async def async_start(self) -> None: ...
    async def async_shutdown(self) -> None: ...
    async def run_instance_by_id(self, instance_id: str) -> dict[str, str]: ...


# 全局调度器实例
adapter: SchedulerProtocol | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # noqa: D401 (fastapi 兼容)
    """应用生命周期：启动调度器 & 关闭清理。"""
    global adapter
    logger.info("Application starting ...")

    # 自动发现并注册所有 collectors
    discover_and_register()

    # 使用新的 RayScheduler 调度器
    logger.info("使用 RayScheduler 调度器")
    adapter = RaySchedulerAdapter()

    # 加载采集器并启动调度器
    adapter.load_all_collectors()

    # 异步启动调度器
    await adapter.async_start()

    logger.info("Scheduler started")

    try:
        yield
    finally:
        logger.info("Application shutting down ...")
        if adapter:
            # 异步关闭调度器
            await adapter.async_shutdown()
            logger.info("Scheduler stopped.")


app = FastAPI(
    title="RayInfo Backend",
    description="RayInfo 跨平台资讯聚合器 API",
    version="1.0.0",
    lifespan=lifespan,
)

# 添加 CORS 支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(api_v1_router)


@app.get("/", summary="健康检查 / Hello")
async def root():
    return {"message": "Hello RayInfo"}


@app.get("/status")
async def get_status() -> dict[str, Any]:
    """获取系统状态信息。

    返回:
        包含系统状态的字典
    """
    status: dict[str, Any] = {
        "message": "RayInfo Backend Service is running",
        "scheduler_type": "RayScheduler",
        "timestamp": datetime.now().isoformat(),
    }

    if adapter and isinstance(adapter, RaySchedulerAdapter):
        from .ray_scheduler.registry import registry

        scheduler = adapter.scheduler
        status.update(
            {
                "scheduler_running": scheduler.is_running(),
                "registered_jobs": len(registry.sources),
                "pending_tasks": len(scheduler._heap),
            }
        )

    return status


@app.get("/instances", summary="列出所有采集器实例")
async def list_instances():
    """列出所有已注册的采集器实例及其ID。

    Returns:
        dict: 包含所有实例信息的字典，键为实例ID，值为实例详情
    """
    instances = instance_manager.list_all_instances()
    return {"total_count": len(instances), "instances": instances}


@app.get("/collectors", summary="按类型分组列出采集器")
async def list_collectors_by_type():
    """按采集器类型分组列出采集器实例。

    Returns:
        dict: 按采集器类型分组的实例信息
    """
    instances = instance_manager.list_all_instances()
    collectors_by_type = {}

    for instance_id, instance_info in instances.items():
        collector_name = instance_info["collector_name"]

        if collector_name not in collectors_by_type:
            collectors_by_type[collector_name] = {
                "collector_name": collector_name,
                "display_name": _get_collector_display_name(collector_name),
                "total_instances": 0,
                "instances": [],
            }

        # 添加实例信息
        instance_detail = {
            "instance_id": instance_id,
            "param": instance_info.get("param"),
            "display_name": _get_instance_display_name(
                collector_name, instance_info.get("param")
            ),
            "status": instance_info.get("status"),
            "health_score": instance_info.get("health_score"),
            "run_count": instance_info.get("run_count", 0),
            "error_count": instance_info.get("error_count", 0),
            "last_run": instance_info.get("last_run"),
            "created_at": instance_info.get("created_at"),
        }

        collectors_by_type[collector_name]["instances"].append(instance_detail)
        collectors_by_type[collector_name]["total_instances"] += 1

    return {
        "total_collectors": len(collectors_by_type),
        "collectors": collectors_by_type,
    }


def _get_collector_display_name(collector_name: str) -> str:
    """获取采集器的显示名称"""
    display_names = {
        "mes.search": "搜索引擎",
        "weibo.home": "微博首页",
        "rss.feed": "RSS订阅",
    }
    return display_names.get(collector_name, collector_name)


def _get_instance_display_name(collector_name: str, param: str | None) -> str:
    """获取实例的显示名称"""
    if param is None:
        # 普通采集器，使用采集器名称
        return _get_collector_display_name(collector_name)
    else:
        # 参数化采集器，使用参数作为显示名称
        return param


@app.get("/trigger/{instance_id}", summary="手动触发采集器实例")
async def trigger_instance(instance_id: str):
    """根据实例ID手动触发采集器执行一次数据收集。

    Args:
        instance_id (str): 采集器实例的唯一ID

    Returns:
        dict: 执行结果，包含状态和消息

    Raises:
        HTTPException: 当实例不存在或执行失败时
    """
    if adapter is None:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    try:
        result = await adapter.run_instance_by_id(instance_id)
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["message"])
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# 可选：uvicorn 直接运行入口
if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("rayinfo_backend.app:app", host="0.0.0.0", port=8000, reload=True)
