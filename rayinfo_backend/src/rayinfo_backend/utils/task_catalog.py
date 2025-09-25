"""Task catalog bridging scheduler state and API expectations.

This replaces the previous InstanceManager by deriving collector instance
information from the running scheduler plus execution history stored in the
scheduler database.  The resulting snapshots keep API compatibility (e.g.
`instance.collector.name`) without requiring the legacy BaseCollector registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import logging
from typing import Any, Callable, Dict, Optional, Tuple

from ..config.settings import Settings, get_settings
from ..models.info_item import CollectorExecutionState, DatabaseManager
from ..ray_scheduler import TaskExecutionManager
from ..ray_scheduler.scheduler import RayScheduler
from ..state import get_scheduler

logger = logging.getLogger("rayinfo.task_catalog")


def _format_timestamp(timestamp: Optional[float]) -> Optional[str]:
    """Convert numeric timestamps into ISO formatted strings."""

    if timestamp is None:
        return None
    try:
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
    except Exception:  # pragma: no cover - defensive formatting
        logger.debug("Failed to format timestamp: %s", timestamp)
        return None


@dataclass(slots=True)
class _CollectorProxy:
    """Mimic the historic collector object that exposed a `.name` attribute."""

    name: str


@dataclass(slots=True)
class InstanceSnapshot:
    """Public representation of a collector instance."""

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
    args: Dict[str, Any] = field(default_factory=dict)

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
            "args": self.args,
        }


class TaskCatalog:
    """Provide access to configured collector instances via the scheduler."""

    def __init__(
        self,
        scheduler_provider: Callable[[], Optional[RayScheduler]] = get_scheduler,
        settings_provider: Callable[[], Settings] = get_settings,
    ) -> None:
        self._scheduler_provider = scheduler_provider
        self._settings_provider = settings_provider
        self._db_manager: DatabaseManager | None = None

    def list_instances(self) -> Dict[str, InstanceSnapshot]:
        """Return all configured collector instances."""

        base_instances = self._build_base_instances()
        if not base_instances:
            return {}

        execution_states = self._load_execution_states()
        instances: Dict[str, InstanceSnapshot] = {}
        for instance_id, base in base_instances.items():
            instances[instance_id] = self._merge_state(base, execution_states)
        return instances

    def get_instance(self, instance_id: str) -> Optional[InstanceSnapshot]:
        """Retrieve a single collector instance."""

        instances = self.list_instances()
        return instances.get(instance_id)

    def get_collector_instances(
        self, collector_name: str
    ) -> Dict[str, InstanceSnapshot]:
        """Return all instances belonging to a specific collector."""

        instances = self.list_instances()
        return {
            instance_id: record
            for instance_id, record in instances.items()
            if record.collector_name == collector_name
        }

    # Internal helpers -------------------------------------------------

    def _build_base_instances(self) -> Dict[str, InstanceSnapshot]:
        instances: Dict[str, InstanceSnapshot] = {}

        scheduler = self._scheduler_provider()
        if scheduler is not None:
            instances.update(self._build_from_scheduler(scheduler))

        self._ensure_config_instances(instances)
        return instances

    def _build_from_scheduler(
        self, scheduler: RayScheduler
    ) -> Dict[str, InstanceSnapshot]:
        snapshot = scheduler.get_tasks_snapshot()
        instances: Dict[str, InstanceSnapshot] = {}
        now_iso = datetime.now(timezone.utc).isoformat()

        for task_id, entry in snapshot.items():
            collector_name = entry.get("source")
            if not collector_name:
                logger.debug("Skipping task without source: id=%s", task_id)
                continue

            args = dict(entry.get("args") or {})
            param_key = entry.get("param_key")
            if param_key is None:
                param_key = TaskExecutionManager.build_param_key(args)

            instances[task_id] = InstanceSnapshot(
                instance_id=task_id,
                collector_name=collector_name,
                param=self._extract_primary_param(args),
                param_key=param_key,
                interval_seconds=entry.get("interval_seconds"),
                engine=args.get("engine"),
                time_range=args.get("time_range"),
                status="idle",
                created_at=now_iso,
                args=args,
            )

        return instances

    def _ensure_config_instances(
        self, instances: Dict[str, InstanceSnapshot]
    ) -> None:
        settings = self._settings_provider()

        # Ensure search engine instances defined in configuration exist.
        for item in settings.search_engine:
            collector_name = "mes.search"
            args = {
                "query": item.query,
                "engine": item.engine,
                "time_range": item.time_range,
            }
            param_key = TaskExecutionManager.build_param_key(args)
            instance_id = self._build_instance_id(collector_name, param_key)
            instances.setdefault(
                instance_id,
                InstanceSnapshot(
                    instance_id=instance_id,
                    collector_name=collector_name,
                    param=item.query,
                    param_key=param_key,
                    interval_seconds=item.interval_seconds,
                    engine=item.engine,
                    time_range=item.time_range,
                ),
            )

        # Optionally expose the built-in weibo collector if configured.
        weibo_interval = settings.weibo_home_interval_seconds
        if weibo_interval and weibo_interval > 0:
            collector_name = "weibo.home"
            instance_id = collector_name
            instances.setdefault(
                instance_id,
                InstanceSnapshot(
                    instance_id=instance_id,
                    collector_name=collector_name,
                    param=None,
                    param_key="",
                    interval_seconds=weibo_interval,
                    status="inactive",
                    health_score=0.0,
                ),
            )

    @staticmethod
    def _build_instance_id(collector_name: str, param_key: str) -> str:
        param_key = (param_key or "").strip()
        return f"{collector_name}:{param_key}" if param_key else collector_name

    @staticmethod
    def _extract_primary_param(args: Dict[str, Any]) -> Optional[str]:
        for key in ("query", "id", "name", "source", "url"):
            value = args.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return None

    def _load_execution_states(self) -> Dict[Tuple[str, str], CollectorExecutionState]:
        db_manager = self._get_db_manager()
        if not db_manager:
            return {}

        try:
            session = db_manager.get_session()
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
        base: InstanceSnapshot,
        execution_states: Dict[Tuple[str, str], CollectorExecutionState],
    ) -> InstanceSnapshot:
        record = replace(base)
        key = (record.collector_name, record.param_key or "")
        state = execution_states.get(key)

        if state is None:
            return record

        record.run_count = state.execution_count
        record.status = "active" if state.execution_count > 0 else base.status
        record.last_run = _format_timestamp(state.last_execution_time)
        record.created_at = _format_timestamp(state.created_at) or base.created_at
        record.updated_at = _format_timestamp(state.updated_at)
        record.health_score = 1.0 if state.execution_count > 0 else base.health_score
        return record

    def _get_db_manager(self) -> Optional[DatabaseManager]:
        if self._db_manager is not None:
            return self._db_manager

        try:
            settings = self._settings_provider()
            self._db_manager = DatabaseManager.get_instance(
                settings.storage.db_path
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to obtain DatabaseManager: %s", exc)
            self._db_manager = None
        return self._db_manager


# Shared catalog used across the application
TaskCatalogSingleton = TaskCatalog()
task_catalog = TaskCatalogSingleton

__all__ = [
    "InstanceSnapshot",
    "TaskCatalog",
    "task_catalog",
]
