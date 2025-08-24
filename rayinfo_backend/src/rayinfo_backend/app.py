"""RayInfo 后端核心骨架

仅包含：
- FastAPI 实例
- APScheduler AsyncIOScheduler 集成（应用启动/关闭生命周期）
- 一个示例周期任务（打印日志）
- 一个 Hello World 路由

后续实际业务（抓取、数据持久化等）在此基础上扩展。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from .utils.logging import setup_logging
from .scheduling.scheduler import SchedulerAdapter
from .collectors import discover_and_register  # 新增: 自动发现 collectors
from .utils.instance_id import instance_manager

logger = setup_logging()

adapter: SchedulerAdapter | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # noqa: D401 (fastapi 兼容)
    """应用生命周期：启动调度器 & 关闭清理。"""
    global adapter
    logger.info("Application starting ...")

    # 自动发现并注册所有 collectors
    discover_and_register()

    adapter = SchedulerAdapter()
    adapter.load_all_collectors()
    adapter.start()
    logger.info("Scheduler started")

    try:
        yield
    finally:
        logger.info("Application shutting down ...")
        if adapter:
            adapter.shutdown()
            logger.info("Scheduler stopped.")


app = FastAPI(title="RayInfo Backend", lifespan=lifespan)


@app.get("/", summary="健康检查 / Hello")
async def root():
    return {"message": "Hello RayInfo"}


@app.get("/instances", summary="列出所有采集器实例")
async def list_instances():
    """列出所有已注册的采集器实例及其ID。

    Returns:
        dict: 包含所有实例信息的字典，键为实例ID，值为实例详情
    """
    instances = instance_manager.list_all_instances()
    return {"total_count": len(instances), "instances": instances}


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
