from __future__ import annotations

from pydantic import BaseModel
from typing import Optional


class TaskDefinition(BaseModel):
    id: str
    collector_name: str
    interval_seconds: int
    enabled: bool = True


class TaskRunContext(BaseModel):
    task_id: str
    started_at: float
