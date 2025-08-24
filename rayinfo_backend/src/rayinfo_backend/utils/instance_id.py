"""实例ID管理器

为采集器实例生成唯一的Hash ID，支持：
- 基于采集器名称和参数的稳定Hash算法
- 实例ID到采集器及参数的映射管理
- 手动调度接口的实例查找功能
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional, Tuple
from dataclasses import dataclass

from ..collectors.base import BaseCollector, ParameterizedCollector


@dataclass
class CollectorInstance:
    """采集器实例信息"""

    collector: BaseCollector
    param: str | None  # None 表示普通采集器
    instance_id: str


class InstanceIDManager:
    """采集器实例ID管理器

    负责生成和管理采集器实例的唯一ID，支持：
    1. 基于采集器名称和参数生成稳定的Hash ID
    2. 维护实例ID到采集器对象的映射关系
    3. 为手动调度提供实例查找功能
    """

    def __init__(self):
        # 实例ID到采集器实例的映射
        self._instances: Dict[str, CollectorInstance] = {}

    def generate_instance_id(
        self, collector_name: str, param: str | None = None
    ) -> str:
        """生成采集器实例的唯一ID

        Args:
            collector_name: 采集器名称，如 "mes.search"
            param: 参数字符串，普通采集器为None，参数化采集器为具体参数值

        Returns:
            str: 8位的16进制Hash ID，如 "a1b2c3d4"

        Note:
            - 相同的采集器名称和参数组合总是生成相同的ID
            - 使用SHA-256算法确保冲突概率极低
            - 截取前8位保持ID简洁易用
        """
        # 创建用于Hash的字符串
        if param is None:
            # 普通采集器：只使用采集器名称
            hash_input = f"collector:{collector_name}"
        else:
            # 参数化采集器：使用采集器名称和参数
            hash_input = f"collector:{collector_name}:param:{param}"

        # 使用SHA-256生成Hash
        hash_obj = hashlib.sha256(hash_input.encode("utf-8"))
        full_hash = hash_obj.hexdigest()

        # 截取前8位作为实例ID
        return full_hash[:8]

    def register_instance(
        self, collector: BaseCollector, param: str | None = None
    ) -> str:
        """注册采集器实例并返回实例ID

        Args:
            collector: 采集器对象
            param: 参数值，普通采集器为None

        Returns:
            str: 生成的实例ID
        """
        instance_id = self.generate_instance_id(collector.name, param)

        # 创建实例信息
        instance = CollectorInstance(
            collector=collector, param=param, instance_id=instance_id
        )

        # 注册到映射表
        self._instances[instance_id] = instance

        return instance_id

    def get_instance(self, instance_id: str) -> CollectorInstance | None:
        """根据实例ID获取采集器实例信息

        Args:
            instance_id: 实例ID

        Returns:
            CollectorInstance | None: 实例信息，如果不存在则返回None
        """
        return self._instances.get(instance_id)

    def list_all_instances(self) -> Dict[str, Dict[str, Any]]:
        """列出所有已注册的实例信息

        Returns:
            Dict[str, Dict[str, Any]]: 实例ID到实例信息的映射
        """
        result = {}
        for instance_id, instance in self._instances.items():
            result[instance_id] = {
                "collector_name": instance.collector.name,
                "param": instance.param,
                "collector_type": (
                    "parameterized"
                    if isinstance(instance.collector, ParameterizedCollector)
                    else "simple"
                ),
            }
        return result

    def clear(self):
        """清空所有实例注册信息（主要用于测试）"""
        self._instances.clear()


# 全局实例管理器
instance_manager = InstanceIDManager()
