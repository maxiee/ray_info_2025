from __future__ import annotations

from pydantic import BaseModel, Field


class Settings(BaseModel):
    scheduler_timezone: str = Field(default="UTC")
    weibo_home_interval_seconds: int = Field(default=60)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
