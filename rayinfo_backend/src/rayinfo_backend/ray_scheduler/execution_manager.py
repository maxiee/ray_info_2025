"""任务执行时间管理器

本模块实现任务执行时间的记录，用于智能调度和断点续传功能。
专注于记录任务的最后执行时间，不持久化待执行任务。
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional

from ..models.info_item import DatabaseManager, CollectorExecutionState

logger = logging.getLogger("rayinfo.task_execution_manager")


class TaskExecutionManager:
    """任务执行时间管理器（单例模式）

    负责记录和管理任务的执行时间，实现智能调度功能。
    通过记录每个任务的最后执行时间，支持冷启动时的智能调度决策。
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_path: str = "rayinfo.db"):
        """单例模式实现

        Args:
            db_path: 数据库文件路径

        Returns:
            TaskExecutionManager: 单例实例
        """
        if cls._instance is None:
            with cls._lock:
                # 双重检查锁定
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str = "rayinfo.db"):
        """初始化任务执行时间管理器

        Args:
            db_path: 数据库文件路径
        """
        # 确保只初始化一次
        if self._initialized:
            return

        self.db_manager = DatabaseManager.get_instance(db_path)

        # 统计信息
        self._stats = {
            "executions_recorded": 0,
            "queries_performed": 0,
        }

        self._initialized = True
        logger.info("任务执行时间管理器初始化完成")

    def _extract_param_key(self, args: Dict[str, Any]) -> str:
        """从任务参数中提取参数键

        Args:
            args: 任务参数字典

        Returns:
            参数键字符串
        """
        if not args:
            return ""

        # 尝试从任务参数中提取有意义的键
        # 通常使用 source（来源）相关的参数作为键
        if "source" in args:
            return str(args["source"])
        elif "url" in args:
            return str(args["url"])
        elif "id" in args:
            return str(args["id"])
        elif "name" in args:
            return str(args["name"])
        else:
            # 如果没有明显的键，使用所有参数的哈希
            import hashlib
            import json

            param_str = json.dumps(args, sort_keys=True)
            return hashlib.md5(param_str.encode()).hexdigest()[:16]

    def record_execution(
        self,
        task_source: str,
        param_key: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        """记录任务执行时间

        Args:
            task_source: 任务源名称
            param_key: 参数键，用于区分参数化任务的不同实例
            timestamp: 执行时间戳，默认使用当前时间
        """
        if timestamp is None:
            timestamp = time.time()

        # 将None转换为空字符串，兼容数据库约束
        if param_key is None:
            param_key = ""

        self._stats["executions_recorded"] += 1

        session = self.db_manager.get_session()
        try:
            # 尝试查找现有记录
            state = (
                session.query(CollectorExecutionState)
                .filter_by(collector_name=task_source, param_key=param_key)
                .first()
            )

            if state:
                # 更新现有记录
                state.last_execution_time = timestamp  # type: ignore
                state.updated_at = timestamp  # type: ignore
                state.execution_count += 1  # type: ignore
                logger.debug(
                    "更新任务执行记录 source=%s param=%s count=%d",
                    task_source,
                    param_key or "(empty)",
                    state.execution_count,
                )
            else:
                # 创建新记录
                state = CollectorExecutionState(
                    collector_name=task_source,
                    param_key=param_key,
                    last_execution_time=timestamp,
                    created_at=timestamp,
                    updated_at=timestamp,
                    execution_count=1,
                )
                session.add(state)
                logger.debug(
                    "创建任务执行记录 source=%s param=%s",
                    task_source,
                    param_key or "(empty)",
                )

            session.commit()

        except Exception as e:
            session.rollback()
            logger.error(
                "记录任务执行时间失败 source=%s param=%s error=%s",
                task_source,
                param_key or "(empty)",
                e,
            )
            raise
        finally:
            session.close()

    def get_last_execution_time(
        self, task_source: str, param_key: Optional[str] = None
    ) -> Optional[float]:
        """获取任务最后执行时间

        Args:
            task_source: 任务源名称
            param_key: 参数键，普通任务传入None

        Returns:
            最后执行时间戳，首次运行返回None
        """
        self._stats["queries_performed"] += 1

        # 将None转换为空字符串，兼容数据库约束
        if param_key is None:
            param_key = ""

        session = self.db_manager.get_session()
        try:
            # 使用复合主键查询
            state = (
                session.query(CollectorExecutionState)
                .filter_by(collector_name=task_source, param_key=param_key)
                .first()
            )

            if state:
                logger.debug(
                    "找到任务执行记录 source=%s param=%s last_time=%f",
                    task_source,
                    param_key or "(empty)",
                    state.last_execution_time,
                )
                return state.last_execution_time  # type: ignore
            else:
                logger.debug(
                    "任务首次运行 source=%s param=%s",
                    task_source,
                    param_key or "(empty)",
                )
                return None

        except Exception as e:
            logger.error(
                "查询任务执行时间失败 source=%s param=%s error=%s",
                task_source,
                param_key or "(empty)",
                e,
            )
            return None
        finally:
            session.close()

    def calculate_next_schedule_time(
        self,
        task_source: str,
        interval_seconds: int,
        param_key: Optional[str] = None,
    ) -> float:
        """计算任务的下次调度时间

        根据最后执行时间和间隔计算下次调度时间。
        这是智能调度的核心方法。

        Args:
            task_source: 任务源名称
            interval_seconds: 调度间隔（秒）
            param_key: 参数键

        Returns:
            下次调度的绝对时间戳
        """
        current_time = time.time()
        last_time = self.get_last_execution_time(task_source, param_key)

        if last_time is None:
            # 首次运行，立即执行
            logger.info(
                "任务首次运行，立即调度 source=%s param=%s",
                task_source,
                param_key or "(empty)",
            )
            return current_time

        # 计算预期的下次执行时间
        expected_next_time = last_time + interval_seconds

        if expected_next_time <= current_time:
            # 已经超时，立即执行
            delay = current_time - expected_next_time
            logger.info(
                "任务超时，立即调度 source=%s param=%s delay=%.1fs",
                task_source,
                param_key or "(empty)",
                delay,
            )
            return current_time
        else:
            # 按计划时间执行
            delay = expected_next_time - current_time
            logger.debug(
                "任务按计划调度 source=%s param=%s delay=%.1fs",
                task_source,
                param_key or "(empty)",
                delay,
            )
            return expected_next_time

    def should_execute_immediately(
        self,
        task_source: str,
        interval_seconds: int,
        param_key: Optional[str] = None,
    ) -> bool:
        """判断是否应该立即执行任务

        Args:
            task_source: 任务源名称
            interval_seconds: 调度间隔（秒）
            param_key: 参数键

        Returns:
            是否应该立即执行
        """
        next_time = self.calculate_next_schedule_time(
            task_source, interval_seconds, param_key
        )
        current_time = time.time()
        return next_time <= current_time

    def cleanup_old_records(self, retention_days: int = 30) -> int:
        """清理过期的执行记录

        Args:
            retention_days: 保留天数

        Returns:
            清理的记录数量
        """
        cutoff_time = time.time() - (retention_days * 24 * 60 * 60)

        session = self.db_manager.get_session()
        try:
            # 删除过期记录（基于updated_at字段）
            deleted_count = (
                session.query(CollectorExecutionState)
                .filter(CollectorExecutionState.updated_at < cutoff_time)
                .delete(synchronize_session=False)
            )

            session.commit()

            if deleted_count > 0:
                logger.info(f"清理了 {deleted_count} 条过期执行记录")

            return deleted_count

        except Exception as e:
            session.rollback()
            logger.error(f"清理执行记录失败: {e}")
            return 0
        finally:
            session.close()

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            **self._stats,
            "db_path": self.db_manager.db_path,
        }

    @classmethod
    def reset_instance(cls):
        """重置单例实例（主要用于测试）"""
        with cls._lock:
            cls._instance = None

    @classmethod
    def get_instance(cls, db_path: str = "rayinfo.db") -> "TaskExecutionManager":
        """获取单例实例的便捷方法

        Args:
            db_path: 数据库文件路径

        Returns:
            TaskExecutionManager: 单例实例
        """
        return cls(db_path)
