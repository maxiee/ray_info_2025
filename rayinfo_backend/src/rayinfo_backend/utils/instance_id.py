"""实例管理器 - 占位符实现

注意：原有的 BaseCollector 实例管理功能已被移除。
这个模块提供兼容性接口，返回空结果。
"""

from typing import Dict, Any, Optional


class PlaceholderInstanceManager:
    """占位符实例管理器

    提供与原实例管理器相同的接口，但返回空结果，
    用于保持 API 兼容性。
    """

    def get_instance(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """获取实例信息

        Args:
            instance_id: 实例ID

        Returns:
            None (实例管理器已移除)
        """
        return None

    def list_all_instances(self) -> Dict[str, Dict[str, Any]]:
        """列出所有实例

        Returns:
            空字典 (实例管理器已移除)
        """
        return {}

    def get_collector_instances(self, collector_name: str) -> Dict[str, Dict[str, Any]]:
        """获取指定采集器的所有实例

        Args:
            collector_name: 采集器名称

        Returns:
            空字典 (实例管理器已移除)
        """
        return {}


# 全局实例管理器实例
instance_manager = PlaceholderInstanceManager()
