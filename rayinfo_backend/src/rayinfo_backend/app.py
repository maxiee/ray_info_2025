"""RayInfo 后端核心骨架

仅包含：
- FastAPI 实例
- APScheduler AsyncIOScheduler 集成（应用启动/关闭生命周期）
- 一个示例周期任务（打印日志）
- 一个 Hello World 路由

后续实际业务（抓取、数据持久化等）在此基础上扩展。
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from .utils.logging import setup_logging
from .scheduling.scheduler import SchedulerAdapter

logger = setup_logging()

adapter: SchedulerAdapter | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # noqa: D401 (fastapi 兼容)
    """应用生命周期：启动调度器 & 关闭清理。"""
    global adapter
    logger.info("Application starting ...")

    # 触发 collectors 注册
    from .collectors import weibo  # noqa: F401

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


async def _shutdown_scheduler():  # 兼容旧接口，暂不使用
    await asyncio.sleep(0.05)


app = FastAPI(title="RayInfo Backend", lifespan=lifespan)


@app.get("/", summary="健康检查 / Hello")
async def root():
    return {"message": "Hello RayInfo"}


# 可选：uvicorn 直接运行入口
if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("rayinfo_backend.app:app", host="0.0.0.0", port=8000, reload=True)
