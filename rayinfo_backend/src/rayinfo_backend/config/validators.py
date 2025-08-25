"""配置验证器模块

提供统一的配置验证机制，确保配置的有效性和一致性。
支持不同类型配置的专门验证逻辑。
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from .settings import Settings, SearchEngineItem, StorageConfig

logger = logging.getLogger("rayinfo.config.validators")


@dataclass
class ValidationResult:
    """验证结果
    
    包含验证是否通过、错误信息和警告信息。
    """
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    
    def __post_init__(self):
        """确保列表不为None"""
        self.errors = self.errors or []
        self.warnings = self.warnings or []
    
    def add_error(self, message: str):
        """添加错误信息"""
        self.errors.append(message)
        self.is_valid = False
    
    def add_warning(self, message: str):
        """添加警告信息"""
        self.warnings.append(message)
    
    def merge(self, other: "ValidationResult"):
        """合并另一个验证结果"""
        if not other.is_valid:
            self.is_valid = False
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


class ConfigValidator(ABC):
    """配置验证器抽象基类
    
    定义了配置验证的统一接口。
    """
    
    @abstractmethod
    def validate(self, config: Any) -> ValidationResult:
        """验证配置
        
        Args:
            config: 要验证的配置对象
            
        Returns:
            验证结果
        """
        raise NotImplementedError


class SearchEngineConfigValidator(ConfigValidator):
    """搜索引擎配置验证器
    
    验证搜索引擎相关配置的有效性。
    """
    
    # 支持的时间范围值
    VALID_TIME_RANGES = {"d", "w", "m", "y"}
    
    # 支持的搜索引擎
    VALID_ENGINES = {"duckduckgo", "google", "bing", "auto"}
    
    def validate(self, config: List[SearchEngineItem]) -> ValidationResult:
        """验证搜索引擎配置列表
        
        Args:
            config: 搜索引擎配置项列表
            
        Returns:
            验证结果
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        if not isinstance(config, list):
            result.add_error("搜索引擎配置必须是列表类型")
            return result
        
        if len(config) == 0:
            result.add_warning("搜索引擎配置为空，不会执行任何搜索任务")
            return result
        
        # 验证每个配置项
        seen_queries = set()
        for i, item in enumerate(config):
            item_result = self._validate_search_item(item, i)
            result.merge(item_result)
            
            # 检查查询重复
            if item.query in seen_queries:
                result.add_warning(f"搜索查询重复: '{item.query}'")
            seen_queries.add(item.query)
        
        return result
    
    def _validate_search_item(self, item: SearchEngineItem, index: int) -> ValidationResult:
        """验证单个搜索引擎配置项
        
        Args:
            item: 搜索引擎配置项
            index: 配置项索引
            
        Returns:
            验证结果
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        prefix = f"搜索引擎配置项 [{index}]"
        
        # 验证查询字符串
        if not item.query or not item.query.strip():
            result.add_error(f"{prefix}: 查询字符串不能为空")
        elif len(item.query.strip()) < 2:
            result.add_warning(f"{prefix}: 查询字符串过短可能影响搜索效果")
        
        # 验证执行间隔
        if item.interval_seconds < 1:
            result.add_error(f"{prefix}: 执行间隔必须大于0秒")
        elif item.interval_seconds < 30:
            result.add_warning(f"{prefix}: 执行间隔过短可能触发反爬机制")
        elif item.interval_seconds > 86400:  # 1天
            result.add_warning(f"{prefix}: 执行间隔过长可能影响信息时效性")
        
        # 验证搜索引擎
        if item.engine not in self.VALID_ENGINES:
            result.add_error(f"{prefix}: 不支持的搜索引擎 '{item.engine}'")
        
        # 验证时间范围
        if item.time_range and item.time_range not in self.VALID_TIME_RANGES:
            result.add_error(f"{prefix}: 无效的时间范围 '{item.time_range}'")
        
        return result


class StorageConfigValidator(ConfigValidator):
    """存储配置验证器
    
    验证存储相关配置的有效性。
    """
    
    def validate(self, config: StorageConfig) -> ValidationResult:
        """验证存储配置
        
        Args:
            config: 存储配置对象
            
        Returns:
            验证结果
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        # 验证数据库路径
        db_path_result = self._validate_db_path(config.db_path)
        result.merge(db_path_result)
        
        # 验证批量处理大小
        if config.batch_size < 1:
            result.add_error("批量处理大小必须大于0")
        elif config.batch_size > 10000:
            result.add_warning("批量处理大小过大可能影响性能")
        elif config.batch_size < 10:
            result.add_warning("批量处理大小过小可能影响效率")
        
        return result
    
    def _validate_db_path(self, db_path: str) -> ValidationResult:
        """验证数据库路径
        
        Args:
            db_path: 数据库文件路径
            
        Returns:
            验证结果
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        if not db_path or not db_path.strip():
            result.add_error("数据库路径不能为空")
            return result
        
        path = Path(db_path)
        
        # 检查父目录
        parent_dir = path.parent
        if not parent_dir.exists():
            try:
                parent_dir.mkdir(parents=True, exist_ok=True)
                result.add_warning(f"创建数据库目录: {parent_dir}")
            except Exception as e:
                result.add_error(f"无法创建数据库目录 {parent_dir}: {e}")
        
        # 检查文件权限
        if path.exists():
            if not path.is_file():
                result.add_error(f"数据库路径不是文件: {db_path}")
            elif not os.access(path, os.R_OK | os.W_OK):
                result.add_error(f"数据库文件无读写权限: {db_path}")
        
        return result


class SchedulerConfigValidator(ConfigValidator):
    """调度器配置验证器
    
    验证调度器相关配置的有效性。
    """
    
    # 支持的时区（简化列表，生产环境应使用完整的时区列表）
    COMMON_TIMEZONES = {
        "UTC", "GMT", "CST", "EST", "PST", "JST", "KST",
        "Asia/Shanghai", "Asia/Tokyo", "America/New_York", 
        "America/Los_Angeles", "Europe/London", "Europe/Berlin"
    }
    
    def validate(self, config: Settings) -> ValidationResult:
        """验证调度器配置
        
        Args:
            config: 设置对象
            
        Returns:
            验证结果
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        # 验证时区
        if config.scheduler_timezone not in self.COMMON_TIMEZONES:
            result.add_warning(f"时区 '{config.scheduler_timezone}' 可能不被支持")
        
        # 验证微博间隔
        if config.weibo_home_interval_seconds < 30:
            result.add_warning("微博首页抓取间隔过短可能触发反爬机制")
        elif config.weibo_home_interval_seconds > 3600:
            result.add_warning("微博首页抓取间隔过长可能影响信息时效性")
        
        return result


class CompositeConfigValidator(ConfigValidator):
    """组合配置验证器
    
    组合多个专门的验证器，提供全面的配置验证。
    """
    
    def __init__(self):
        """初始化组合验证器"""
        self.search_engine_validator = SearchEngineConfigValidator()
        self.storage_validator = StorageConfigValidator()
        self.scheduler_validator = SchedulerConfigValidator()
    
    def validate(self, config: Settings) -> ValidationResult:
        """验证完整的设置配置
        
        Args:
            config: 设置对象
            
        Returns:
            综合验证结果
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        # 验证搜索引擎配置
        search_result = self.search_engine_validator.validate(config.search_engine)
        result.merge(search_result)
        
        # 验证存储配置
        storage_result = self.storage_validator.validate(config.storage)
        result.merge(storage_result)
        
        # 验证调度器配置
        scheduler_result = self.scheduler_validator.validate(config)
        result.merge(scheduler_result)
        
        # 记录验证结果
        if result.errors:
            logger.error(f"配置验证发现 {len(result.errors)} 个错误")
            for error in result.errors:
                logger.error(f"  - {error}")
        
        if result.warnings:
            logger.warning(f"配置验证发现 {len(result.warnings)} 个警告")
            for warning in result.warnings:
                logger.warning(f"  - {warning}")
        
        if result.is_valid and not result.warnings:
            logger.info("配置验证通过")
        
        return result


def validate_settings(settings: Settings) -> ValidationResult:
    """验证设置配置的便捷函数
    
    Args:
        settings: 设置对象
        
    Returns:
        验证结果
    """
    validator = CompositeConfigValidator()
    return validator.validate(settings)


# 导入os模块（为了数据库路径验证）
import os