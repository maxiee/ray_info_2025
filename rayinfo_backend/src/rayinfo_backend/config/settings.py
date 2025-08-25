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
    time_range: Optional[str] = Field(
        default=None,
        pattern="^[dwmy]$",
        description="时间范围过滤：d=天, w=周, m=月, y=年"
    )


class StorageConfig(BaseModel):
    """存储配置模型

    定义数据库相关配置，包括数据库路径、批量处理大小等。
    """

    db_path: str = Field(
        default="./data/rayinfo.db", description="SQLite 数据库文件路径"
    )
    
    def __init__(self, **data):
        super().__init__(**data)
        # 支持环境变量覆盖数据库路径
        if "RAYINFO_DB_PATH" in os.environ:
            self.db_path = os.environ["RAYINFO_DB_PATH"]
    batch_size: int = Field(default=100, ge=1, description="批量处理大小")
    enable_wal: bool = Field(
        default=True, description="是否启用 WAL 模式（提升并发性能）"
    )


class Settings(BaseModel):
    scheduler_timezone: str = Field(default="UTC")
    weibo_home_interval_seconds: int = Field(default=60)
    # 新结构：search_engine 是一个任务列表
    search_engine: List[SearchEngineItem] = Field(default_factory=list)
    # 存储配置
    storage: StorageConfig = Field(default_factory=StorageConfig)

    @staticmethod
    def from_yaml(path: Path | str) -> "Settings":
        """从 YAML 文件加载配置（已弃用，使用 from_config_loaders 代替）
        
        Args:
            path: YAML 文件路径
            
        Returns:
            Settings 实例
        """
        import warnings
        warnings.warn(
            "from_yaml 方法已弃用，请使用 from_config_loaders，"
            "将在下一个版本中移除",
            DeprecationWarning,
            stacklevel=2
        )
        
        # 为向后兼容，使用新的加载器实现
        from .loaders import YamlConfigLoader, ConfigParser
        loader = YamlConfigLoader(path)
        config_data = loader.load()
        return ConfigParser.parse(config_data)
    
    @staticmethod
    def from_config_loaders() -> "Settings":
        """使用新的配置加载器模式加载配置
        
        按优先级顺序合并多个配置源：默认配置 < YAML文件 < 环境变量
        
        Returns:
            Settings 实例
        """
        from .loaders import create_default_config_loader, ConfigParser
        
        loader = create_default_config_loader()
        config_data = loader.load()
        return ConfigParser.parse(config_data)


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
    """获取全局配置实例
    
    使用新的配置加载器模式，支持多配置源合并。
    
    Returns:
        Settings实例
    """
    global _settings
    if _settings is None:
        _settings = Settings.from_config_loaders()
    return _settings
