"""线程安全的采集器实例 ID 管理器

提供线程安全的实例管理、生命周期管理和健康监控。
支持并发访问和自动清理过期实例。
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from ..collectors.base import BaseCollector


class InstanceStatus(Enum):
    """实例状态枚举"""

    ACTIVE = "active"  # 活跃状态
    INACTIVE = "inactive"  # 非活跃状态
    ERROR = "error"  # 错误状态
    EXPIRED = "expired"  # 过期状态


@dataclass
class CollectorInstance:
    """增强的采集器实例信息

    包含完整的生命周期管理和状态追踪。
    """

    collector: BaseCollector
    param: str | None  # None 表示普通采集器
    instance_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_run: datetime | None = None
    last_success: datetime | None = None
    last_error: datetime | None = None
    run_count: int = 0
    error_count: int = 0
    status: InstanceStatus = InstanceStatus.ACTIVE

    def update_run_stats(self, success: bool = True, error_msg: str | None = None):
        """更新运行统计

        Args:
            success: 是否成功
            error_msg: 错误信息（如果有）
        """
        now = datetime.utcnow()
        self.last_run = now
        self.run_count += 1

        if success:
            self.last_success = now
            # 成功后重置状态为活跃
            if self.status == InstanceStatus.ERROR:
                self.status = InstanceStatus.ACTIVE
        else:
            self.last_error = now
            self.error_count += 1
            self.status = InstanceStatus.ERROR

    def is_expired(self, max_idle_hours: int = 24) -> bool:
        """检查实例是否过期

        Args:
            max_idle_hours: 最大空闲时间（小时）

        Returns:
            是否过期
        """
        if self.last_run is None:
            # 从未运行的实例，检查创建时间
            idle_time = datetime.utcnow() - self.created_at
        else:
            idle_time = datetime.utcnow() - self.last_run

        return idle_time > timedelta(hours=max_idle_hours)

    def get_health_score(self) -> float:
        """获取实例健康分数

        Returns:
            0.0-1.0 的健康分数
        """
        if self.run_count == 0:
            return 1.0  # 新实例认为健康

        success_rate = (self.run_count - self.error_count) / self.run_count

        # 根据状态调整分数
        if self.status == InstanceStatus.ERROR:
            success_rate *= 0.5
        elif self.status == InstanceStatus.EXPIRED:
            success_rate *= 0.1

        return max(0.0, min(1.0, success_rate))


class InstanceIDManager:
    """线程安全的采集器实例 ID 管理器

    提供线程安全的实例管理、生命周期管理和健康监控。
    支持并发访问和自动清理过期实例。
    """

    def __init__(self, max_idle_hours: int = 24, cleanup_interval: int = 3600):
        """初始化实例管理器

        Args:
            max_idle_hours: 实例最大空闲时间（小时）
            cleanup_interval: 清理间隔（秒）
        """
        # 实例 ID 到采集器实例的映射
        self._instances: Dict[str, CollectorInstance] = {}

        # 线程安全锁（读写锁）
        self._lock = threading.RLock()  # 可重入锁

        # 配置参数
        self.max_idle_hours = max_idle_hours
        self.cleanup_interval = cleanup_interval

        # 上次清理时间
        self._last_cleanup = time.time()

        # 统计信息
        self._stats = {
            "total_created": 0,
            "total_cleaned": 0,
            "last_cleanup_at": None,
        }

    def generate_instance_id(
        self, collector_name: str, param: str | None = None
    ) -> str:
        """生成采集器实例的唯一 ID

        线程安全的 ID 生成，支持冲突检测和重试。

        Args:
            collector_name: 采集器名称，如 "mes.search"
            param: 参数字符串，普通采集器为 None

        Returns:
            str: 8 位的 16 进制 Hash ID，如 "a1b2c3d4"
        """
        with self._lock:
            base_hash = self._compute_base_hash(collector_name, param)

            # 检查冲突并重试
            attempt = 0
            max_attempts = 100  # 防止无限循环

            while attempt < max_attempts:
                if attempt == 0:
                    candidate_id = base_hash[:8]
                else:
                    # 添加随机后缀解决冲突
                    suffix_input = f"{base_hash}:{attempt}:{time.time()}"
                    suffix_hash = hashlib.sha256(
                        suffix_input.encode("utf-8")
                    ).hexdigest()
                    candidate_id = suffix_hash[:8]

                # 检查是否已存在
                if candidate_id not in self._instances:
                    return candidate_id

                attempt += 1

            # 如果达到最大尝试次数，使用时间戳生成唯一 ID
            timestamp_id = hashlib.sha256(
                f"{base_hash}:{time.time()}".encode()
            ).hexdigest()[:8]
            return timestamp_id

    def _compute_base_hash(self, collector_name: str, param: str | None) -> str:
        """计算基础哈希值"""
        if param is None:
            hash_input = f"collector:{collector_name}"
        else:
            hash_input = f"collector:{collector_name}:param:{param}"

        hash_obj = hashlib.sha256(hash_input.encode("utf-8"))
        return hash_obj.hexdigest()

    def register_instance(
        self, collector: BaseCollector, param: str | None = None
    ) -> str:
        """注册采集器实例并返回实例 ID

        线程安全的实例注册，支持重复注册和自动清理。

        Args:
            collector: 采集器对象
            param: 参数值，普通采集器为 None

        Returns:
            str: 生成的实例 ID
        """
        with self._lock:
            # 检查是否需要清理
            self._auto_cleanup_if_needed()

            instance_id = self.generate_instance_id(collector.name, param)

            # 创建实例信息
            instance = CollectorInstance(
                collector=collector, param=param, instance_id=instance_id
            )

            # 注册到映射表
            self._instances[instance_id] = instance
            self._stats["total_created"] += 1

            return instance_id

    def get_instance(self, instance_id: str) -> CollectorInstance | None:
        """根据实例 ID 获取采集器实例信息

        Args:
            instance_id: 实例 ID

        Returns:
            CollectorInstance | None: 实例信息，如果不存在则返回 None
        """
        with self._lock:
            return self._instances.get(instance_id)

    def update_instance_stats(
        self, instance_id: str, success: bool = True, error_msg: str | None = None
    ) -> bool:
        """更新实例运行统计

        Args:
            instance_id: 实例 ID
            success: 是否成功
            error_msg: 错误信息（如果有）

        Returns:
            bool: 是否更新成功
        """
        with self._lock:
            instance = self._instances.get(instance_id)
            if instance:
                instance.update_run_stats(success, error_msg)
                return True
            return False

    def unregister_instance(self, instance_id: str) -> bool:
        """手动注销实例

        Args:
            instance_id: 实例 ID

        Returns:
            bool: 是否成功注销
        """
        with self._lock:
            if instance_id in self._instances:
                del self._instances[instance_id]
                return True
            return False

    def list_all_instances(self) -> Dict[str, Dict[str, Any]]:
        """列出所有已注册的实例信息

        Returns:
            Dict[str, Dict[str, Any]]: 实例 ID 到实例信息的映射
        """
        with self._lock:
            result = {}
            for instance_id, instance in self._instances.items():
                result[instance_id] = {
                    "collector_name": instance.collector.name,
                    "param": instance.param,
                    "collector_type": (
                        "parameterized"
                        if hasattr(instance.collector, "list_param_jobs")
                        and callable(getattr(instance.collector, "list_param_jobs"))
                        and instance.collector.list_param_jobs() is not None
                        else "simple"
                    ),
                    "created_at": instance.created_at.isoformat(),
                    "last_run": (
                        instance.last_run.isoformat() if instance.last_run else None
                    ),
                    "run_count": instance.run_count,
                    "error_count": instance.error_count,
                    "status": instance.status.value,
                    "health_score": instance.get_health_score(),
                    "is_expired": instance.is_expired(self.max_idle_hours),
                }
            return result

    def cleanup_expired_instances(self, force: bool = False) -> int:
        """清理过期实例

        Args:
            force: 是否强制清理（忽略时间间隔）

        Returns:
            int: 清理的实例数量
        """
        with self._lock:
            expired_ids = []

            for instance_id, instance in self._instances.items():
                if instance.is_expired(self.max_idle_hours):
                    instance.status = InstanceStatus.EXPIRED
                    expired_ids.append(instance_id)

            # 移除过期实例
            for instance_id in expired_ids:
                del self._instances[instance_id]

            if expired_ids:
                self._stats["total_cleaned"] += len(expired_ids)
                self._stats["last_cleanup_at"] = datetime.utcnow().isoformat()
                self._last_cleanup = time.time()

            return len(expired_ids)

    def _auto_cleanup_if_needed(self):
        """检查是否需要自动清理"""
        current_time = time.time()
        if current_time - self._last_cleanup > self.cleanup_interval:
            cleaned_count = self.cleanup_expired_instances()
            if cleaned_count > 0:
                import logging

                logger = logging.getLogger("rayinfo.instance_manager")
                logger.info(f"自动清理了 {cleaned_count} 个过期实例")

    def get_stats(self) -> Dict[str, Any]:
        """获取管理器统计信息

        Returns:
            统计信息字典
        """
        with self._lock:
            stats = self._stats.copy()
            stats.update(
                {
                    "active_instances": len(self._instances),
                    "max_idle_hours": self.max_idle_hours,
                    "cleanup_interval": self.cleanup_interval,
                    "last_auto_cleanup": self._last_cleanup,
                }
            )

            # 统计各状态的实例数
            status_counts = {}
            health_scores = []

            for instance in self._instances.values():
                status = instance.status.value
                status_counts[status] = status_counts.get(status, 0) + 1
                health_scores.append(instance.get_health_score())

            stats["status_distribution"] = status_counts

            if health_scores:
                stats["avg_health_score"] = sum(health_scores) / len(health_scores)
            else:
                stats["avg_health_score"] = 1.0

            return stats

    def clear(self):
        """清空所有实例注册信息（主要用于测试）"""
        with self._lock:
            self._instances.clear()
            self._stats = {
                "total_created": 0,
                "total_cleaned": 0,
                "last_cleanup_at": None,
            }


# 全局实例管理器
instance_manager = InstanceIDManager()
