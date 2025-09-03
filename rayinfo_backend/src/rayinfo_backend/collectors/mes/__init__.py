"""MES 搜索收集器模块

提供基于 mes CLI 的多搜索引擎数据收集功能。

主要组件：
- MesCollector: 主要的搜索数据收集器
- mes_executor: 提供协程安全的 mes 命令执行机制
"""

from .search import MesCollector
from .mes_executor import execute_mes_command

__all__ = ["MesCollector", "execute_mes_command"]
