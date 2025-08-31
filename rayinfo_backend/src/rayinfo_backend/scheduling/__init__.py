"""Scheduling package public API.

Primary entrypoint:
- SchedulerAdapter: Orchestrates collectors, state, and APScheduler.

Utilities:
- CollectorStateManager: Persistent state & resume.
- JobKind, make_job_id: Unified job identifiers.
"""

from .scheduler import SchedulerAdapter
from .state_manager import CollectorStateManager
from .types import JobKind, make_job_id

__all__ = [
    "SchedulerAdapter",
    "CollectorStateManager",
    "JobKind",
    "make_job_id",
]
