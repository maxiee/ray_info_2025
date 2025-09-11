from __future__ import annotations

from pydantic import BaseModel, Field
from pathlib import Path
import yaml
from typing import List, Optional
import logging
import os

logger = logging.getLogger("rayinfo.config")


class SearchEngineItem(BaseModel):
    query: str
    interval_seconds: int = Field(ge=1)
    engine: str = Field(default="duckduckgo")
    time_range: Optional[str] = Field(default=None)


class StateManagementConfig(BaseModel):
    enable_time_persistence: bool = Field(default=True)
    cleanup_old_states: bool = Field(default=True)
    state_retention_days: int = Field(default=30, ge=1, le=365)


class StorageConfig(BaseModel):
    db_path: str = Field(default="./data/rayinfo.db")
    batch_size: int = Field(default=100, ge=1)
    enable_wal: bool = Field(default=True)
    state_management: StateManagementConfig = Field(
        default_factory=StateManagementConfig
    )

    def __init__(self, **data):
        super().__init__(**data)
        # 支持环境变量覆盖数据库路径
        if "RAYINFO_DB_PATH" in os.environ:
            self.db_path = os.environ["RAYINFO_DB_PATH"]


class Settings(BaseModel):
    scheduler_timezone: str = Field(default="UTC")
    weibo_home_interval_seconds: int = Field(default=60)
    search_engine: List[SearchEngineItem] = Field(default_factory=list)
    storage: StorageConfig = Field(default_factory=StorageConfig)

    @staticmethod
    def from_yaml(path: Optional[Path | str] = None) -> "Settings":
        """从 YAML 文件加载配置"""
        if path is None:
            path = _discover_yaml_path()

        path = Path(path)
        if not path.exists():
            logger.warning(f"配置文件不存在: {path}")
            return Settings()

        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            # 解析搜索引擎配置
            search_engine_items = []
            for item_data in data.get("search_engine", []):
                if isinstance(item_data, dict):
                    try:
                        search_engine_items.append(SearchEngineItem(**item_data))
                    except Exception as e:
                        logger.warning(
                            f"跳过无效的搜索引擎配置项: {item_data}, 错误: {e}"
                        )

            # 解析存储配置
            storage_data = data.get("storage", {})
            storage_config = StorageConfig(**storage_data)

            return Settings(
                scheduler_timezone=data.get("scheduler_timezone", "UTC"),
                weibo_home_interval_seconds=data.get("weibo_home_interval_seconds", 60),
                search_engine=search_engine_items,
                storage=storage_config,
            )

        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return Settings()


def _discover_yaml_path() -> Path:
    """向上递归查找 rayinfo.yaml 文件"""
    start = Path(__file__).resolve()
    for parent in start.parents:
        candidate = parent / "rayinfo.yaml"
        if candidate.exists():
            return candidate
    # 默认位置
    return Path(__file__).resolve().parent.parent.parent / "rayinfo.yaml"


_settings: Settings | None = None


def get_settings() -> Settings:
    """获取全局配置实例"""
    global _settings
    if _settings is None:
        _settings = Settings.from_yaml()
    return _settings
