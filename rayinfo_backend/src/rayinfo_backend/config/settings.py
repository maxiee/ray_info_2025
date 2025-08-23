from __future__ import annotations

from pydantic import BaseModel, Field
from pathlib import Path
import yaml
from typing import List, Optional
import logging

logger = logging.getLogger("rayinfo.config")


class SearchEngineItem(BaseModel):
    query: str
    interval_seconds: int = Field(ge=1)
    engine: str = Field(default="duckduckgo")


class StorageConfig(BaseModel):
    """存储配置模型
    
    定义数据库相关配置，包括数据库路径、批量处理大小等。
    """
    db_path: str = Field(default="./data/rayinfo.db", description="SQLite 数据库文件路径")
    batch_size: int = Field(default=100, ge=1, description="批量处理大小")
    enable_wal: bool = Field(default=True, description="是否启用 WAL 模式（提升并发性能）")


class Settings(BaseModel):
    scheduler_timezone: str = Field(default="UTC")
    weibo_home_interval_seconds: int = Field(default=60)
    # 新结构：search_engine 是一个任务列表
    search_engine: List[SearchEngineItem] = Field(default_factory=list)
    # 存储配置
    storage: StorageConfig = Field(default_factory=StorageConfig)

    @staticmethod
    def from_yaml(path: Path | str) -> "Settings":
        p = Path(path)
        if not p.exists():
            # 返回默认，允许缺省文件
            return Settings()
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        # 兼容：顶层 scheduler.timezone
        scheduler_tz = data.get("scheduler", {}).get("timezone")
        # 新结构优先: 顶层 search_engine
        search_engine_list_raw = data.get("search_engine")
        # 存储配置
        storage_config_raw = data.get("storage", {})
        items: List[SearchEngineItem] = []
        if isinstance(search_engine_list_raw, list):
            for obj in search_engine_list_raw:
                try:
                    items.append(SearchEngineItem(**obj))
                except Exception as e:  # pragma: no cover - 容错日志
                    logger.warning(
                        "invalid search_engine item skipped=%s error=%s", obj, e
                    )
        settings = Settings(
            scheduler_timezone=scheduler_tz or "UTC",
            search_engine=items,
            storage=StorageConfig(**storage_config_raw) if storage_config_raw else StorageConfig(),
        )
        return settings


_settings: Settings | None = None


def _discover_settings_path() -> Path:
    """Try to locate rayinfo.yaml by walking parents.

    原实现假设: settings.py 上三级目录存在 rayinfo.yaml (即 src 同级). 实际仓库结构:
    repo_root/
      rayinfo_backend/            <-- rayinfo.yaml 在这里
        rayinfo.yaml
        src/rayinfo_backend/config/settings.py

    因此原路径指向 src/rayinfo.yaml, 文件不存在 -> 使用默认配置, 导致 MesCollector 查询列表为空，
    调度器认为没有参数化任务。
    本函数向上逐级寻找第一个包含 rayinfo.yaml 的目录。
    """
    start = Path(__file__).resolve()
    for parent in start.parents:
        candidate = parent / "rayinfo.yaml"
        if candidate.exists():
            return candidate
    # fallback (保持原逻辑，尽管很可能不存在)
    return Path(__file__).resolve().parent.parent.parent / "rayinfo.yaml"


_settings_path: Path = _discover_settings_path()
logger.debug(
    "settings yaml resolved path=%s exists=%s", _settings_path, _settings_path.exists()
)


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        # 约定：仓库根目录（包上三层）包含 rayinfo.yaml
        _settings = Settings.from_yaml(_settings_path)
    return _settings
