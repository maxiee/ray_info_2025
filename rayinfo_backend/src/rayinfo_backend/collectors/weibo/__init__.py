from __future__ import annotations

from ..base import registry, BaseCollector


def register_weibo(c: BaseCollector):  # 简单封装, 未来可添加平台级初始化
    registry.register(c)


# 导入具体 collector 以触发注册 (在 app 启动时 import)
from . import home  # noqa: E402,F401
