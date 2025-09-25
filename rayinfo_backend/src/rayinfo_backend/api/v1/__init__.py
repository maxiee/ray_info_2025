"""API v1 包初始化模块。

保持对外导入简洁，将具体路由实现委托给 `routes` 模块。
"""

from __future__ import annotations

from .routes import router

__all__ = ["router"]
