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
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger("rayinfo")
logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] %(levelname)s %(name)s: %(message)s"
)

# 全局调度器（也可改为依赖注入方式）
scheduler: AsyncIOScheduler | None = None


def demo_job():
    """示例定时任务：打印心跳。实际项目中替换为抓取等逻辑。"""
    logger.info("[demo_job] heartbeat")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # noqa: D401 (fastapi 兼容)
    """应用生命周期：启动调度器 & 关闭清理。"""
    global scheduler
    logger.info("Application starting ...")

    # 初始化调度器
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        demo_job, IntervalTrigger(seconds=30), id="demo_job", replace_existing=True
    )
    scheduler.start()
    logger.info("Scheduler started with jobs: %s", scheduler.get_jobs())

    try:
        yield
    finally:
        logger.info("Application shutting down ...")
        if scheduler:
            # 优雅关闭：等待正在运行的 job 完成（可设置超时）
            await _shutdown_scheduler(scheduler)
            logger.info("Scheduler stopped.")


async def _shutdown_scheduler(s: AsyncIOScheduler):
    s.shutdown(wait=False)
    # 等待短暂时间让后台任务收尾（根据需要调整）
    await asyncio.sleep(0.1)


app = FastAPI(title="RayInfo Backend", lifespan=lifespan)


@app.get("/", summary="健康检查 / Hello")
async def root():
    return {"message": "Hello RayInfo"}


# 可选：uvicorn 直接运行入口
if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("rayinfo_backend.app:app", host="0.0.0.0", port=8000, reload=True)
