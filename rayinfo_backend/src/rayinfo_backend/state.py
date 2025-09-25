"""Shared runtime state for the RayInfo backend.

Currently exposes the global RayScheduler instance so that
request handlers and services can access it without importing
`app` directly, avoiding circular dependencies during startup.
"""

from __future__ import annotations

from typing import Optional

from .ray_scheduler import RayScheduler

# Mutable module level reference to the running scheduler.
_scheduler: Optional[RayScheduler] = None


def get_scheduler() -> Optional[RayScheduler]:
    """Return the active RayScheduler instance, if available."""

    return _scheduler


def set_scheduler(instance: Optional[RayScheduler]) -> None:
    """Update the shared scheduler reference."""

    global _scheduler
    _scheduler = instance


__all__ = ["get_scheduler", "set_scheduler"]
