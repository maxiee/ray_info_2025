from __future__ import annotations

from datetime import datetime, timezone

from rayinfo_backend.config.settings import SearchEngineItem, Settings, StorageConfig
from rayinfo_backend.models.info_item import CollectorExecutionState, DatabaseManager
from rayinfo_backend.ray_scheduler import TaskExecutionManager
from rayinfo_backend.utils.task_catalog import TaskCatalog


class FakeScheduler:
    def __init__(self, snapshot):
        self._snapshot = snapshot

    def get_tasks_snapshot(self):
        return self._snapshot


def _build_settings(db_path: str) -> Settings:
    return Settings(
        scheduler_timezone="UTC",
        weibo_home_interval_seconds=120,
        search_engine=[
            SearchEngineItem(
                query="example query",
                interval_seconds=300,
                engine="google",
                time_range="d",
            )
        ],
        storage=StorageConfig(db_path=db_path),
    )


def test_task_catalog_builds_instances(tmp_path):
    DatabaseManager.reset_instance()
    db_path = tmp_path / "rayinfo.db"
    settings = _build_settings(str(db_path))

    args = {
        "query": "example query",
        "engine": "google",
        "time_range": "d",
    }
    param_key = TaskExecutionManager.build_param_key(args)
    task_id = f"mes.search:{param_key}"

    snapshot = {
        task_id: {
            "source": "mes.search",
            "args": args,
            "interval_seconds": 300,
            "next_run_at": datetime.now(timezone.utc),
            "param_key": param_key,
        }
    }

    catalog = TaskCatalog(
        scheduler_provider=lambda: FakeScheduler(snapshot),
        settings_provider=lambda: settings,
    )

    instances = catalog.list_instances()

    assert task_id in instances
    instance = instances[task_id]
    assert instance.collector_name == "mes.search"
    assert instance.param == "example query"
    assert instance.engine == "google"

    # Configured weibo collector should be exposed even if not scheduled.
    assert "weibo.home" in instances
    assert instances["weibo.home"].status == "inactive"


def test_task_catalog_merges_execution_state(tmp_path):
    DatabaseManager.reset_instance()
    db_path = tmp_path / "rayinfo.db"
    settings = _build_settings(str(db_path))

    # No scheduler tasks: rely on configuration fallback.
    catalog = TaskCatalog(
        scheduler_provider=lambda: None,
        settings_provider=lambda: settings,
    )

    args = {
        "query": "example query",
        "engine": "google",
        "time_range": "d",
    }
    param_key = TaskExecutionManager.build_param_key(args)
    instance_id = f"mes.search:{param_key}"

    session = DatabaseManager.get_instance(str(db_path)).get_session()
    try:
        timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()
        state = CollectorExecutionState(
            collector_name="mes.search",
            param_key=param_key,
            last_execution_time=timestamp,
            created_at=timestamp,
            updated_at=timestamp,
            execution_count=5,
        )
        session.add(state)
        session.commit()
    finally:
        session.close()

    instances = catalog.list_instances()
    record = instances[instance_id]

    assert record.run_count == 5
    assert record.status == "active"
    assert record.last_run is not None
    assert record.last_run.endswith("+00:00")
