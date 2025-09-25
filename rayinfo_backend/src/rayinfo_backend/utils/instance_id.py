"""Collector instance manager bridging configuration and API expectations.

The previous implementation removed the legacy BaseCollector instance registry
and returned empty results.  This broke API consumers that rely on `/collectors`
and instance based filtering.  The new implementation rebuilds an in-memory
view of configured collector instances using the declarative configuration and
execution state persisted in the scheduler database.

It keeps a lightweight, API friendly representation that mimics the historic
interface (e.g. `instance.collector.name`) so the rest of the codebase can keep
working without large scale refactoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import logging
import threading
from typing import Any, Dict, Optional, Tuple

from ..config.settings import get_settings
from ..models.info_item import CollectorExecutionState, DatabaseManager
from ..ray_scheduler.execution_manager import TaskExecutionManager

logger = logging.getLogger("rayinfo.instance_manager")


def _format_timestamp(timestamp: Optional[float]) -> Optional[str]:
    """Convert numeric timestamps into ISO formatted strings."""

    if timestamp is None:
        return None
    try:
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
    except Exception:
        logger.debug("Failed to format timestamp: %s", timestamp)
        return None


@dataclass(slots=True)
class _CollectorProxy:
    """Mimic the historic collector object that exposed a `.name` attribute."""

    name: str


@dataclass(slots=True)
class InstanceRecord:
    """Internal representation of a collector instance."""

    instance_id: str
    collector_name: str
    param: Optional[str]
    param_key: str
    interval_seconds: Optional[int]
    engine: Optional[str] = None
    time_range: Optional[str] = None
    status: str = "idle"
    health_score: float = 1.0
    run_count: int = 0
    error_count: int = 0
    last_run: Optional[str] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: Optional[str] = None

    @property
    def collector(self) -> _CollectorProxy:
        return _CollectorProxy(self.collector_name)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a plain dictionary for API responses."""

        return {
            "instance_id": self.instance_id,
            "collector_name": self.collector_name,
            "param": self.param,
            "param_key": self.param_key,
            "interval_seconds": self.interval_seconds,
            "engine": self.engine,
            "time_range": self.time_range,
            "status": self.status,
            "health_score": self.health_score,
            "run_count": self.run_count,
            "error_count": self.error_count,
            "last_run": self.last_run,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class InstanceManager:
    """Provide access to configured collector instances."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._base_instances: Dict[str, InstanceRecord] | None = None
        self._db_manager: DatabaseManager | None = None

    def _ensure_initialized(self) -> None:
        if self._base_instances is not None:
            return

        with self._lock:
            if self._base_instances is not None:
                return

            settings = get_settings()
            self._db_manager = DatabaseManager.get_instance(
                settings.storage.db_path
            )

            instances: Dict[str, InstanceRecord] = {}

            # Build instances for search engine collectors (mes.search)
            for item in settings.search_engine:
                collector_name = "mes.search"
                args = {
                    "query": item.query,
                    "engine": item.engine,
                    "time_range": item.time_range,
                }
                param_key = TaskExecutionManager.build_param_key(args)
                instance_id = self._build_instance_id(collector_name, param_key)
                instances[instance_id] = InstanceRecord(
                    instance_id=instance_id,
                    collector_name=collector_name,
                    param=item.query,
                    param_key=param_key,
                    interval_seconds=item.interval_seconds,
                    engine=item.engine,
                    time_range=item.time_range,
                )

            # Optionally expose the built-in weibo collector if configured
            weibo_interval = settings.weibo_home_interval_seconds
            if weibo_interval and weibo_interval > 0:
                collector_name = "weibo.home"
                instance_id = collector_name
                instances.setdefault(
                    instance_id,
                    InstanceRecord(
                        instance_id=instance_id,
                        collector_name=collector_name,
                        param=None,
                        param_key="",
                        interval_seconds=weibo_interval,
                        status="inactive",  # scheduler may not yet run it
                        health_score=0.0,
                    ),
                )

            self._base_instances = instances

    @staticmethod
    def _build_instance_id(collector_name: str, param_key: str) -> str:
        param_key = (param_key or "").strip()
        return f"{collector_name}:{param_key}" if param_key else collector_name

    def _load_execution_states(self) -> Dict[Tuple[str, str], CollectorExecutionState]:
        if not self._db_manager:
            return {}

        try:
            session = self._db_manager.get_session()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to obtain DB session: %s", exc)
            return {}

        try:
            records = (
                session.query(CollectorExecutionState).all()  # type: ignore[attr-defined]
            )
            result: Dict[Tuple[str, str], CollectorExecutionState] = {}
            for record in records:
                key = (record.collector_name, record.param_key or "")
                result[key] = record
            return result
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to query execution states: %s", exc)
            return {}
        finally:
            session.close()

    def _merge_state(
        self,
        base: InstanceRecord,
        execution_states: Dict[Tuple[str, str], CollectorExecutionState],
    ) -> InstanceRecord:
        record = replace(base)
        key = (record.collector_name, record.param_key or "")
        state = execution_states.get(key)

        if state is None:
            return record
        record.run_count = state.execution_count
        record.status = "active" if state.execution_count > 0 else base.status
        record.last_run = _format_timestamp(state.last_execution_time)
        record.created_at = (
            _format_timestamp(state.created_at) or base.created_at
        )
        record.updated_at = _format_timestamp(state.updated_at)
        # Healthy until we have real health metrics
        record.health_score = 1.0 if state.execution_count > 0 else base.health_score
        return record

    def list_all_instances(self) -> Dict[str, InstanceRecord]:
        """Return all configured collector instances."""

        self._ensure_initialized()
        if not self._base_instances:
            return {}

        execution_states = self._load_execution_states()
        instances: Dict[str, InstanceRecord] = {}
        for instance_id, base in self._base_instances.items():
            enriched = self._merge_state(base, execution_states)
            instances[instance_id] = enriched
        return instances

    def get_instance(self, instance_id: str) -> Optional[InstanceRecord]:
        """Retrieve a single collector instance."""

        instances = self.list_all_instances()
        return instances.get(instance_id)

    def get_collector_instances(
        self, collector_name: str
    ) -> Dict[str, InstanceRecord]:
        """Return all instances belonging to a specific collector."""

        instances = self.list_all_instances()
        return {
            instance_id: record
            for instance_id, record in instances.items()
            if record.collector_name == collector_name
        }


# Shared instance used across the application
instance_manager = InstanceManager()
