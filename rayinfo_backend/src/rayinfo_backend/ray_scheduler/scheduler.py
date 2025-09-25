"""RayScheduler: 简化版的定时任务调度器

该实现采用数据驱动思路：
- 应用启动时将定时任务与历史执行记录加载到内存字典中
- 由一个固定 1 秒 tick 的定时循环检查任务字典
- 每个 tick 最多执行一个到期任务，其余任务顺延至下一次 tick

相比上一版基于最小堆和信号量的实现，这里刻意降低了抽象层级，
以换取更好的可读性和便于未来对外暴露任务表。
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional, Tuple

from .task import Task
from .registry import registry
from .execution_manager import TaskExecutionManager


class RayScheduler:
    """数据驱动的简化调度器"""

    def __init__(
        self,
        enable_execution_tracking: bool = True,
        db_path: str = "rayinfo.db",
        tick_interval: float = 1.0,
    ):
        """初始化调度器

        Args:
            enable_execution_tracking: 是否启用执行时间记录
            db_path: 数据库文件路径
            tick_interval: 定时循环的周期，单位秒
        """
        self._tick_interval = max(0.1, tick_interval)
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None

        # 执行时间记录
        self._enable_execution_tracking = enable_execution_tracking
        self._execution_manager = None
        if enable_execution_tracking:
            self._execution_manager = TaskExecutionManager.get_instance(db_path)

        # 日志记录器
        self._log = logging.getLogger("rayinfo.ray_scheduler")

    def load_tasks(self, definitions: Iterable[Dict[str, Any]]) -> None:
        """加载任务定义并生成内存任务表。

        Args:
            definitions: 每个元素包含 source/args/interval_seconds 的字典。
                可选字段：param_key、task_id、start_at。
        """
        tasks: Dict[str, Dict[str, Any]] = {}
        now = datetime.now(timezone.utc)

        for raw in definitions:
            try:
                source = raw["source"]
                interval_seconds = raw.get("interval_seconds")
                args = raw.get("args", {}) or {}
            except KeyError as e:
                self._log.warning("任务定义缺少字段，跳过: %s | error=%s", raw, e)
                continue

            param_key = raw.get("param_key")
            if param_key is None and args:
                param_key = TaskExecutionManager.build_param_key(args)

            task_id = raw.get("task_id") or self._build_task_id(source, param_key)

            next_run_at = raw.get("start_at")
            if isinstance(next_run_at, datetime) and next_run_at.tzinfo is None:
                next_run_at = next_run_at.replace(tzinfo=timezone.utc)

            if next_run_at is None:
                next_run_at = self._calculate_initial_schedule(
                    source,
                    interval_seconds,
                    param_key,
                    now,
                )

            tasks[task_id] = {
                "source": source,
                "args": args,
                "interval_seconds": interval_seconds,
                "next_run_at": next_run_at,
                "param_key": param_key,
            }

            self._log.info(
                "加载任务: id=%s source=%s next_run=%s interval=%s",
                task_id,
                source,
                next_run_at,
                interval_seconds,
            )

        self._tasks = tasks

    async def start(self) -> None:
        """启动调度器主循环（幂等）"""
        if self._running:
            self._log.warning("Scheduler already running")
            return

        self._running = True
        self._loop_task = asyncio.create_task(self._timer_loop())
        self._log.info("Scheduler started")

    async def stop(self) -> None:
        """有序停止调度器"""
        if not self._running:
            self._log.warning("Scheduler not running")
            return

        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._loop_task
            self._loop_task = None

        self._log.info("Scheduler stopped")

    async def _timer_loop(self) -> None:
        """每秒扫描任务表并执行到期任务"""
        self._log.info("Scheduler timer loop started")
        try:
            while self._running:
                await self._execute_due_task()
                await asyncio.sleep(self._tick_interval)
        except asyncio.CancelledError:
            self._log.debug("Scheduler timer loop cancelled")
            raise
        except Exception as exc:  # pragma: no cover - 兜底保护
            self._log.exception("Scheduler timer loop error: %s", exc)
        finally:
            self._log.info("Scheduler timer loop stopped")

    async def _execute_due_task(self) -> None:
        picked = self._pick_due_entry()
        if not picked:
            return

        task_id, entry = picked

        task = Task(
            source=entry["source"],
            args=dict(entry["args"]),
            schedule_at=entry["next_run_at"],
            interval=entry["interval_seconds"],
        )

        consumer = registry.find(entry["source"])
        if consumer is None:
            self._log.error("未知的任务源，跳过执行: %s", entry["source"])
            self._reschedule_entry(task_id, entry, success=False)
            return

        self._log.info(
            "执行任务: id=%s source=%s due=%s",
            task_id,
            entry["source"],
            entry["next_run_at"],
        )

        try:
            await consumer.consume(task)
            if self._enable_execution_tracking and self._execution_manager:
                self._execution_manager.record_execution(
                    entry["source"], entry["param_key"]
                )
            self._reschedule_entry(task_id, entry, success=True)
            self._log.info("任务完成: id=%s", task_id)
        except Exception as exc:  # pragma: no cover - 避免任务抛出导致循环停止
            self._log.exception(
                "任务执行失败: id=%s source=%s error=%s",
                task_id,
                entry["source"],
                exc,
            )
            self._reschedule_entry(task_id, entry, success=False)

    def _pick_due_entry(self) -> Optional[Tuple[str, Dict[str, Any]]]:
        now = datetime.now(timezone.utc)
        due = [
            (task_id, entry)
            for task_id, entry in self._tasks.items()
            if entry["next_run_at"] <= now
        ]

        if not due:
            return None

        return min(due, key=lambda item: item[1]["next_run_at"])

    def _reschedule_entry(
        self, task_id: str, entry: Dict[str, Any], *, success: bool
    ) -> None:
        interval_seconds = entry.get("interval_seconds")
        if interval_seconds is None or interval_seconds <= 0:
            self._tasks.pop(task_id, None)
            self._log.info("移除一次性任务: id=%s", task_id)
            return

        base_time = datetime.now(timezone.utc)
        entry["next_run_at"] = base_time + timedelta(seconds=interval_seconds)
        status = "success" if success else "fail"
        self._log.debug(
            "重排任务: id=%s status=%s next_run=%s",
            task_id,
            status,
            entry["next_run_at"],
        )

    def get_queue_size(self) -> int:
        """获取当前任务表中的任务数量"""
        return len(self._tasks)

    def is_running(self) -> bool:
        return self._running

    def get_next_task_time(self) -> Optional[datetime]:
        """获取下一个要执行的任务时间"""
        if not self._tasks:
            return None

        return min(entry["next_run_at"] for entry in self._tasks.values())

    def get_tasks_snapshot(self) -> Dict[str, Dict[str, Any]]:
        """返回任务表快照，方便未来对外暴露"""
        return {
            task_id: {
                "source": entry["source"],
                "args": entry["args"],
                "interval_seconds": entry["interval_seconds"],
                "next_run_at": entry["next_run_at"],
                "param_key": entry["param_key"],
            }
            for task_id, entry in self._tasks.items()
        }

    def _calculate_initial_schedule(
        self,
        source: str,
        interval_seconds: Optional[int],
        param_key: Optional[str],
        fallback_time: datetime,
    ) -> datetime:
        if (
            not self._enable_execution_tracking
            or not self._execution_manager
            or interval_seconds is None
            or interval_seconds <= 0
        ):
            return fallback_time

        timestamp = self._execution_manager.calculate_next_schedule_time(
            source, interval_seconds, param_key
        )
        return datetime.fromtimestamp(timestamp, timezone.utc)

    @staticmethod
    def _build_task_id(source: str, param_key: Optional[str]) -> str:
        cleaned = (param_key or "").strip()
        return f"{source}:{cleaned}" if cleaned else source
