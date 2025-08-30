"""采集器状态管理器

本模块实现采集器执行状态的持久化管理，提供断点续传功能。
支持普通采集器和参数化采集器两种模式的状态跟踪。
"""

from __future__ import annotations

import time
import threading
import logging
from typing import Optional

from ..models.info_item import DatabaseManager, CollectorExecutionState

logger = logging.getLogger("rayinfo.state_manager")


class CollectorStateManager:
    """采集器状态管理器（单例模式）

    负责管理所有采集器的执行状态，实现断点续传功能。
    通过记录和查询每个采集器实例的最后执行时间，支持智能调度决策。
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_path: str = "rayinfo.db"):
        """单例模式实现

        Args:
            db_path: 数据库文件路径

        Returns:
            CollectorStateManager: 单例实例
        """
        if cls._instance is None:
            with cls._lock:
                # 双重检查锁定
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str = "rayinfo.db"):
        """初始化状态管理器

        Args:
            db_path: 数据库文件路径
        """
        # 确保只初始化一次
        if self._initialized:
            return

        self.db_manager = DatabaseManager.get_instance(db_path)

        # 状态管理统计
        self._stats = {
            "queries_count": 0,
            "updates_count": 0,
            "cache_hits": 0,
        }

        self._initialized = True
        logger.info("采集器状态管理器初始化完成")

    def get_last_execution_time(
        self, collector_name: str, param_key: Optional[str] = None
    ) -> Optional[float]:
        """获取采集器最后执行时间

        Args:
            collector_name: 采集器名称
            param_key: 参数键，普通采集器传入None

        Returns:
            最后执行时间戳，首次运行返回None
        """
        self._stats["queries_count"] += 1

        # 将None转换为空字符串，兼容数据库约束
        if param_key is None:
            param_key = ""

        session = self.db_manager.get_session()
        try:
            # 使用复合主键查询
            state = (
                session.query(CollectorExecutionState)
                .filter_by(collector_name=collector_name, param_key=param_key)
                .first()
            )

            if state:
                logger.debug(
                    "找到采集器状态记录 collector=%s param=%s last_time=%f",
                    collector_name,
                    param_key or "(empty)",
                    state.last_execution_time,
                )
                return state.last_execution_time  # type: ignore
            else:
                logger.debug(
                    "采集器首次运行 collector=%s param=%s",
                    collector_name,
                    param_key or "(empty)",
                )
                return None

        except Exception as e:
            logger.error(
                "查询采集器状态失败 collector=%s param=%s error=%s",
                collector_name,
                param_key or "(empty)",
                e,
            )
            return None
        finally:
            session.close()

    def update_execution_time(
        self,
        collector_name: str,
        param_key: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        """更新采集器执行时间

        使用UPSERT操作确保幂等性，自动处理首次插入和后续更新。

        Args:
            collector_name: 采集器名称
            param_key: 参数键，普通采集器传入None
            timestamp: 执行时间戳，默认使用当前时间
        """
        if timestamp is None:
            timestamp = time.time()

        # 将None转换为空字符串，兼容数据库约束
        if param_key is None:
            param_key = ""

        self._stats["updates_count"] += 1

        session = self.db_manager.get_session()
        try:
            # 尝试查找现有记录
            state = (
                session.query(CollectorExecutionState)
                .filter_by(collector_name=collector_name, param_key=param_key)
                .first()
            )

            if state:
                # 更新现有记录
                state.last_execution_time = timestamp  # type: ignore
                state.updated_at = timestamp  # type: ignore
                state.execution_count += 1  # type: ignore
                logger.debug(
                    "更新采集器状态 collector=%s param=%s count=%d",
                    collector_name,
                    param_key or "(empty)",
                    state.execution_count,
                )
            else:
                # 创建新记录
                state = CollectorExecutionState(
                    collector_name=collector_name,
                    param_key=param_key,
                    last_execution_time=timestamp,
                    created_at=timestamp,
                    updated_at=timestamp,
                    execution_count=1,
                )
                session.add(state)
                logger.debug(
                    "创建采集器状态记录 collector=%s param=%s",
                    collector_name,
                    param_key or "(empty)",
                )

            session.commit()

        except Exception as e:
            session.rollback()
            logger.error(
                "更新采集器状态失败 collector=%s param=%s error=%s",
                collector_name,
                param_key or "(empty)",
                e,
            )
            raise
        finally:
            session.close()

    def should_run_immediately(
        self,
        collector_name: str,
        param_key: Optional[str] = None,
        interval_seconds: int = 300,
    ) -> bool:
        """判断是否应该立即执行采集器

        业务逻辑：
        1. 首次运行 -> 立即执行
        2. 当前时间与上次执行时间的差值 > 1个调度间隔 -> 立即执行
        3. 否则 -> 正常调度

        Args:
            collector_name: 采集器名称
            param_key: 参数键
            interval_seconds: 调度间隔（秒）

        Returns:
            bool: 是否应该立即执行
        """
        # 将None转换为空字符串
        if param_key is None:
            param_key = ""

        last_time = self.get_last_execution_time(collector_name, param_key)

        # 首次运行
        if last_time is None:
            logger.info(
                "采集器首次运行，立即执行 collector=%s param=%s",
                collector_name,
                param_key or "(empty)",
            )
            return True

        # 检查时间差
        current_time = time.time()
        time_diff = current_time - last_time

        if time_diff > interval_seconds:
            logger.info(
                "采集器超时，立即执行 collector=%s param=%s time_diff=%.1f interval=%d",
                collector_name,
                param_key or "(empty)",
                time_diff,
                interval_seconds,
            )
            return True
        else:
            logger.debug(
                "采集器正常调度 collector=%s param=%s time_diff=%.1f interval=%d",
                collector_name,
                param_key or "(empty)",
                time_diff,
                interval_seconds,
            )
            return False

    def calculate_next_run_time(
        self,
        collector_name: str,
        param_key: Optional[str] = None,
        interval_seconds: int = 300,
    ) -> float:
        """计算下次运行时间

        Args:
            collector_name: 采集器名称
            param_key: 参数键
            interval_seconds: 调度间隔（秒）

        Returns:
            下次运行的绝对时间戳
        """
        # 将None转换为空字符串
        if param_key is None:
            param_key = ""

        last_time = self.get_last_execution_time(collector_name, param_key)
        current_time = time.time()

        if last_time is None:
            # 首次运行，立即执行
            return current_time

        # 计算预期的下次执行时间
        expected_next_time = last_time + interval_seconds

        if expected_next_time <= current_time:
            # 已经超时，立即执行
            return current_time
        else:
            # 按计划时间执行
            delay = expected_next_time - current_time
            logger.debug(
                "采集器延迟执行 collector=%s param=%s delay=%.1f",
                collector_name,
                param_key or "(empty)",
                delay,
            )
            return expected_next_time

    def get_collector_stats(
        self, collector_name: str, param_key: Optional[str] = None
    ) -> Optional[dict]:
        """获取采集器统计信息

        Args:
            collector_name: 采集器名称
            param_key: 参数键

        Returns:
            采集器统计信息字典，不存在时返回None
        """
        # 将None转换为空字符串
        if param_key is None:
            param_key = ""

        session = self.db_manager.get_session()
        try:
            state = (
                session.query(CollectorExecutionState)
                .filter_by(collector_name=collector_name, param_key=param_key)
                .first()
            )

            if state:
                current_time = time.time()
                return {
                    "collector_name": state.collector_name,
                    "param_key": state.param_key or None,  # 返回时转换回 None
                    "execution_count": state.execution_count,
                    "last_execution_time": state.last_execution_time,
                    "created_at": state.created_at,
                    "updated_at": state.updated_at,
                    "time_since_last_run": current_time - state.last_execution_time,
                }
            return None

        except Exception as e:
            logger.error(
                "获取采集器统计失败 collector=%s param=%s error=%s",
                collector_name,
                param_key or "(empty)",
                e,
            )
            return None
        finally:
            session.close()

    def cleanup_old_states(self, retention_days: int = 30) -> int:
        """清理过期的状态记录

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
                .delete()
            )

            session.commit()

            if deleted_count > 0:
                logger.info(f"清理了 {deleted_count} 条过期状态记录")

            return deleted_count

        except Exception as e:
            session.rollback()
            logger.error(f"清理状态记录失败: {e}")
            return 0
        finally:
            session.close()

    def get_stats(self) -> dict:
        """获取状态管理器统计信息"""
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
    def get_instance(cls, db_path: str = "rayinfo.db") -> "CollectorStateManager":
        """获取单例实例的便捷方法

        Args:
            db_path: 数据库文件路径

        Returns:
            CollectorStateManager: 单例实例
        """
        return cls(db_path)
