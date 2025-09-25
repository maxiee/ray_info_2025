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
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Protocol

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from rayinfo_backend.collectors.mes.mes_executor import MesExecutor
from rayinfo_backend.ray_scheduler import registry
from rayinfo_backend.config.settings import get_settings

from .utils.logging import setup_logging
from .api.v1 import router as api_v1_router
from .ray_scheduler import RayScheduler

logger = setup_logging()

# 全局调度器实例
scheduler: RayScheduler | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # noqa: D401 (fastapi 兼容)
    """应用生命周期：启动调度器 & 关闭清理。"""
    global scheduler
    logger.info("Application starting ...")

    # 解析配置文件（尽早进行，以便初始化数据库路径等依赖）
    settings = get_settings()

    # 注册 TaskConsumer
    registry.register(MesExecutor())

    # 准备调度任务定义
    task_definitions = [
        {
            "source": "mes.search",
            "interval_seconds": item.interval_seconds,
            "args": {
                "query": item.query,
                "engine": item.engine,
                "time_range": item.time_range,
            },
        }
        for item in settings.search_engine
    ]

    # 初始化调度器并加载任务表
    scheduler = RayScheduler(db_path=settings.storage.db_path)
    try:
        scheduler.load_tasks(task_definitions)
        await scheduler.start()
        logger.info(
            "RayScheduler started with %d tasks", scheduler.get_queue_size()
        )
    except Exception as exc:
        logger.exception("Failed to initialise scheduler: %s", exc)
        raise

    logger.info("Application started")

    try:
        yield
    finally:
        logger.info("Application shutting down ...")
        if scheduler:
            await scheduler.stop()
            logger.info("RayScheduler stopped.")
            scheduler = None


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
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scheduler_running": scheduler.is_running() if scheduler else False,
        "registered_jobs": 0,
        "pending_tasks": 0,
    }

    if scheduler:
        snapshot = scheduler.get_tasks_snapshot()
        status["registered_jobs"] = len(snapshot)

        now = datetime.now(timezone.utc)
        status["pending_tasks"] = sum(
            1 for entry in snapshot.values() if entry["next_run_at"] <= now
        )

        next_task_time = scheduler.get_next_task_time()
        if next_task_time:
            status["next_task_time"] = next_task_time.isoformat()
    return status


@app.get("/instances", summary="列出所有采集器实例")
async def list_instances():
    """列出所有已注册的采集器实例及其ID。

    Returns:
        dict: 包含所有实例信息的字典，键为实例ID，值为实例详情
    """
    # 注意：实例管理器已移除，返回空的结果
    return {
        "total_count": 0,
        "instances": {},
        "message": "Instance manager removed with BaseCollector",
    }


@app.get("/collectors", summary="按类型分组列出采集器")
async def list_collectors_by_type():
    """按采集器类型分组列出采集器实例。

    Returns:
        dict: 按采集器类型分组的实例信息
    """
    # 注意：采集器管理器已移除，返回空的结果
    return {
        "total_collectors": 0,
        "collectors": {},
        "message": "Collector management removed with BaseCollector",
    }


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
    # 注意：手动触发功能已移除
    raise HTTPException(
        status_code=501,
        detail="Manual trigger functionality removed with BaseCollector",
    )


# 可选：uvicorn 直接运行入口
if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("rayinfo_backend.app:app", host="0.0.0.0", port=8000, reload=True)
