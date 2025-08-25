"""配置加载器模块

使用策略模式重构配置管理，分离YAML、环境变量等不同配置源的加载逻辑。
提供统一的配置合并和验证机制，简化复杂的兼容性处理。
"""

from __future__ import annotations

import logging
import os
import yaml
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional

from .settings import Settings, SearchEngineItem, StorageConfig

logger = logging.getLogger("rayinfo.config.loaders")


class ConfigLoader(ABC):
    """配置加载器抽象基类
    
    定义了配置加载的统一接口，支持多种配置源。
    """
    
    @abstractmethod
    def load(self) -> Dict[str, Any]:
        """加载配置数据
        
        Returns:
            配置数据字典
        """
        raise NotImplementedError
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查配置源是否可用
        
        Returns:
            配置源是否可用
        """
        raise NotImplementedError


class YamlConfigLoader(ConfigLoader):
    """YAML配置文件加载器
    
    负责从YAML文件中加载配置，支持文件发现和兼容性处理。
    """
    
    def __init__(self, file_path: Path | str | None = None):
        """初始化YAML配置加载器
        
        Args:
            file_path: YAML文件路径，如果为None则自动发现
        """
        self.file_path = Path(file_path) if file_path else self._discover_config_path()
        logger.debug(f"YAML配置文件路径: {self.file_path}")
    
    def _discover_config_path(self) -> Path:
        """自动发现配置文件路径
        
        从当前目录开始向上递归查找rayinfo.yaml文件。
        
        Returns:
            配置文件路径
        """
        start = Path(__file__).resolve()
        for parent in start.parents:
            candidate = parent / "rayinfo.yaml"
            if candidate.exists():
                logger.info(f"发现配置文件: {candidate}")
                return candidate
        
        # 回退到默认位置
        fallback_path = Path(__file__).resolve().parent.parent.parent / "rayinfo.yaml"
        logger.warning(f"未找到配置文件，使用默认路径: {fallback_path}")
        return fallback_path
    
    def is_available(self) -> bool:
        """检查YAML文件是否存在"""
        return self.file_path.exists()
    
    def load(self) -> Dict[str, Any]:
        """加载YAML配置文件
        
        Returns:
            配置数据字典
        """
        if not self.is_available():
            logger.warning(f"配置文件不存在: {self.file_path}")
            return {}
        
        try:
            content = self.file_path.read_text(encoding="utf-8")
            data = yaml.safe_load(content) or {}
            logger.info(f"成功加载配置文件: {self.file_path}")
            return data
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return {}


class EnvironmentConfigLoader(ConfigLoader):
    """环境变量配置加载器
    
    从环境变量中加载配置，支持配置覆盖。
    """
    
    def __init__(self, prefix: str = "RAYINFO_"):
        """初始化环境变量加载器
        
        Args:
            prefix: 环境变量前缀
        """
        self.prefix = prefix
    
    def is_available(self) -> bool:
        """检查是否有相关环境变量"""
        return any(key.startswith(self.prefix) for key in os.environ)
    
    def load(self) -> Dict[str, Any]:
        """从环境变量加载配置
        
        Returns:
            环境变量配置字典
        """
        config = {}
        
        for key, value in os.environ.items():
            if key.startswith(self.prefix):
                # 移除前缀并转换为小写
                config_key = key[len(self.prefix):].lower()
                
                # 处理特殊配置项
                if config_key == "db_path":
                    config.setdefault("storage", {})["db_path"] = value
                elif config_key == "timezone":
                    config["scheduler_timezone"] = value
                else:
                    config[config_key] = value
        
        if config:
            logger.info(f"从环境变量加载了 {len(config)} 个配置项")
        
        return config


class DefaultConfigLoader(ConfigLoader):
    """默认配置加载器
    
    提供系统默认配置值。
    """
    
    def is_available(self) -> bool:
        """默认配置总是可用"""
        return True
    
    def load(self) -> Dict[str, Any]:
        """加载默认配置
        
        Returns:
            默认配置字典
        """
        return {
            "scheduler_timezone": "UTC",
            "weibo_home_interval_seconds": 60,
            "search_engine": [],
            "storage": {
                "db_path": "./data/rayinfo.db",
                "batch_size": 100,
                "enable_wal": True,
            }
        }


class CompositeConfigLoader(ConfigLoader):
    """组合配置加载器
    
    按优先级顺序合并多个配置源的数据。
    """
    
    def __init__(self, loaders: List[ConfigLoader]):
        """初始化组合加载器
        
        Args:
            loaders: 配置加载器列表，按优先级从低到高排序
        """
        self.loaders = loaders
    
    def is_available(self) -> bool:
        """检查是否有任何可用的配置源"""
        return any(loader.is_available() for loader in self.loaders)
    
    def load(self) -> Dict[str, Any]:
        """按优先级合并所有配置源
        
        Returns:
            合并后的配置字典
        """
        merged_config = {}
        
        for loader in self.loaders:
            if loader.is_available():
                try:
                    config = loader.load()
                    merged_config = self._deep_merge(merged_config, config)
                    logger.debug(f"合并配置: {type(loader).__name__}")
                except Exception as e:
                    logger.error(f"配置加载失败 {type(loader).__name__}: {e}")
        
        return merged_config
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """深度合并两个配置字典
        
        Args:
            base: 基础配置字典
            override: 覆盖配置字典
            
        Returns:
            合并后的配置字典
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result


class ConfigParser:
    """配置解析器
    
    负责将原始配置数据转换为Settings对象，处理兼容性和验证。
    """
    
    @staticmethod
    def parse(config_data: Dict[str, Any]) -> Settings:
        """解析配置数据为Settings对象
        
        Args:
            config_data: 原始配置数据
            
        Returns:
            Settings对象
        """
        try:
            # 处理搜索引擎配置兼容性
            search_engine_items = ConfigParser._parse_search_engine_config(
                config_data.get("search_engine", [])
            )
            
            # 处理存储配置
            storage_config = ConfigParser._parse_storage_config(
                config_data.get("storage", {})
            )
            
            # 创建Settings对象
            settings = Settings(
                scheduler_timezone=config_data.get("scheduler_timezone", "UTC"),
                weibo_home_interval_seconds=config_data.get("weibo_home_interval_seconds", 60),
                search_engine=search_engine_items,
                storage=storage_config
            )
            
            # 验证配置
            from .validators import validate_settings
            validation_result = validate_settings(settings)
            
            if not validation_result.is_valid:
                logger.error("配置验证失败，但仍将使用该配置")
                # 注意：即使验证失败，我们仍然返回配置，但会记录错误
                # 这样可以避免因配置问题导致系统完全无法启动
            
            logger.info(f"配置解析完成，搜索引擎任务数: {len(search_engine_items)}")
            return settings
            
        except Exception as e:
            logger.error(f"配置解析失败: {e}")
            # 返回默认配置
            return Settings()
    
    @staticmethod
    def _parse_search_engine_config(search_engine_data: Any) -> List[SearchEngineItem]:
        """解析搜索引擎配置
        
        Args:
            search_engine_data: 搜索引擎配置数据
            
        Returns:
            搜索引擎配置项列表
        """
        items = []
        
        if isinstance(search_engine_data, list):
            for item_data in search_engine_data:
                if isinstance(item_data, dict):
                    try:
                        item = SearchEngineItem(**item_data)
                        items.append(item)
                    except Exception as e:
                        logger.warning(f"跳过无效的搜索引擎配置项: {item_data}, 错误: {e}")
        
        return items
    
    @staticmethod
    def _parse_storage_config(storage_data: Dict[str, Any]) -> StorageConfig:
        """解析存储配置
        
        Args:
            storage_data: 存储配置数据
            
        Returns:
            存储配置对象
        """
        try:
            return StorageConfig(**storage_data)
        except Exception as e:
            logger.warning(f"存储配置解析失败，使用默认配置: {e}")
            return StorageConfig()


def create_default_config_loader() -> CompositeConfigLoader:
    """创建默认的配置加载器
    
    按优先级顺序：默认配置 < YAML文件 < 环境变量
    
    Returns:
        配置加载器实例
    """
    loaders = [
        DefaultConfigLoader(),  # 最低优先级
        YamlConfigLoader(),     # 中等优先级
        EnvironmentConfigLoader(),  # 最高优先级
    ]
    
    return CompositeConfigLoader(loaders)
