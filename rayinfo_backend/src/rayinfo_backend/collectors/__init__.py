from __future__ import annotations

"""Collectors 包初始化与自动发现工具.

提供 discover_and_register():
 - 扫描本包内所有模块
 - 找到 BaseCollector 的具体子类 (排除 BaseCollector 自身)
 - 未实例化过则实例化并注册到全局 registry
 - 记录注册日志，避免重复

可多次调用，重复类名不会重复注册。
"""

from importlib import import_module
import inspect
import logging
import pkgutil
from types import ModuleType

from .base import BaseCollector, SimpleCollector, ParameterizedCollector, registry

logger = logging.getLogger("rayinfo.collectors")


def _iter_modules(package_name: str):
    pkg = import_module(package_name)
    if not hasattr(pkg, "__path__"):
        return
    for modinfo in pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + "."):
        yield modinfo.name


_registered_classes: set[str] = set()


def discover_and_register(package_root: str = __name__):
    """自动发现并注册所有 BaseCollector 子类.

    参数 package_root: 要扫描的包前缀，默认当前包 (rayinfo_backend.collectors)
    """
    count_new = 0
    for module_name in _iter_modules(package_root) or []:
        try:
            mod: ModuleType = import_module(module_name)
        except Exception as e:  # pragma: no cover - 仅日志
            logger.warning("import module failed: %s error=%s", module_name, e)
            continue
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            # 跳过非 BaseCollector 子类和抽象基类
            if not issubclass(obj, BaseCollector):
                continue
            # 跳过抽象基类：BaseCollector, SimpleCollector, ParameterizedCollector
            if obj in (BaseCollector, SimpleCollector, ParameterizedCollector):
                continue
            # 跳过其他抽象类（通过检查是否有未实现的抽象方法）
            if getattr(obj, "__abstractmethods__", None):
                logger.debug(
                    "跳过抽象类: %s.%s (有未实现的抽象方法: %s)",
                    obj.__module__,
                    obj.__name__,
                    obj.__abstractmethods__,
                )
                continue
            qual = f"{obj.__module__}.{obj.__name__}"
            if qual in _registered_classes:
                continue
            try:
                instance = obj()  # 假设无参数构造; 若未来需要参数, 可扩展工厂登记
                registry.register(instance)
                _registered_classes.add(qual)
                count_new += 1
                logger.info(
                    "collector registered: name=%s class=%s", instance.name, qual
                )
            except Exception as e:  # pragma: no cover - 仅日志
                logger.error("register collector failed: class=%s error=%s", qual, e)
    logger.info(
        "collector discovery done: new=%d total=%d", count_new, len(registry.all())
    )


__all__ = ["discover_and_register", "registry", "BaseCollector"]
