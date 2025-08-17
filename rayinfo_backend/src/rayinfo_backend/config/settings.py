from __future__ import annotations

from pydantic import BaseModel, Field, validator
from pathlib import Path
import yaml
from typing import List, Optional
import logging

logger = logging.getLogger("rayinfo.config")


class MesPerQueryOverride(BaseModel):
    query: str
    interval_seconds: Optional[int] = Field(default=None, ge=1)
    engine: Optional[str] = None


class MesSearchConfig(BaseModel):
    interval_seconds: int = Field(default=300, ge=1, description="默认所有查询间隔秒数")
    engine: str = Field(default="duckduckgo")
    queries: List[str] = Field(default_factory=list)
    per_query: List[MesPerQueryOverride] = Field(
        default_factory=list, description="对单个 query 的覆盖配置"
    )

    def iter_query_jobs(self):
        """Yield (query, interval_seconds, engine)."""
        override_map: dict[str, MesPerQueryOverride] = {
            o.query: o for o in self.per_query
        }
        for q in self.queries:
            ov = override_map.get(q)
            yield (
                q,
                (
                    ov.interval_seconds
                    if ov and ov.interval_seconds
                    else self.interval_seconds
                ),
                (ov.engine if ov and ov.engine else self.engine),
            )


class SearchConfig(BaseModel):
    mes: MesSearchConfig = Field(default_factory=MesSearchConfig)


class Settings(BaseModel):
    scheduler_timezone: str = Field(default="UTC")
    weibo_home_interval_seconds: int = Field(default=60)
    search: SearchConfig = Field(default_factory=SearchConfig)

    @staticmethod
    def from_yaml(path: Path | str) -> "Settings":
        p = Path(path)
        if not p.exists():
            # 返回默认，允许缺省文件
            return Settings()
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        # 兼容：顶层 scheduler.timezone
        scheduler_tz = data.get("scheduler", {}).get("timezone")
        search_cfg = data.get("search", {})
        settings = Settings(
            scheduler_timezone=scheduler_tz or "UTC",
            search=SearchConfig(
                mes=MesSearchConfig(**(search_cfg.get("mes", {}) or {}))
            ),
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
