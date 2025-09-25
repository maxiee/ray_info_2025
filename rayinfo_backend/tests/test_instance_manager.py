from __future__ import annotations

from datetime import datetime, timezone

import pytest

from rayinfo_backend.config.settings import SearchEngineItem, Settings, StorageConfig
from rayinfo_backend.models.info_item import CollectorExecutionState, DatabaseManager
from rayinfo_backend.utils.instance_id import InstanceManager


@pytest.fixture(name="custom_settings")
def fixture_custom_settings(tmp_path):
    """Build a Settings object backed by a temporary SQLite database."""

    db_path = tmp_path / "rayinfo.db"
    storage = StorageConfig(db_path=str(db_path))
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
        storage=storage,
    )


def test_instance_manager_builds_instances(monkeypatch, custom_settings):
    monkeypatch.setattr(
        "rayinfo_backend.utils.instance_id.get_settings",
        lambda: custom_settings,
    )
    DatabaseManager.reset_instance()

    manager = InstanceManager()
    instances = manager.list_all_instances()

    assert instances, "expected configured instances"

    search_instances = [
        record
        for record in instances.values()
        if record.collector_name == "mes.search"
    ]
    assert len(search_instances) == 1
    assert search_instances[0].param == "example query"

    weibo_instance = instances.get("weibo.home")
    assert weibo_instance is not None
    assert weibo_instance.status == "inactive"
    assert weibo_instance.interval_seconds == 120


def test_instance_manager_merges_execution_state(monkeypatch, custom_settings):
    monkeypatch.setattr(
        "rayinfo_backend.utils.instance_id.get_settings",
        lambda: custom_settings,
    )
    DatabaseManager.reset_instance()

    manager = InstanceManager()
    instances = manager.list_all_instances()

    record = next(
        r for r in instances.values() if r.collector_name == "mes.search"
    )

    session = DatabaseManager.get_instance(custom_settings.storage.db_path).get_session()
    try:
        timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()
        state = CollectorExecutionState(
            collector_name=record.collector_name,
            param_key=record.param_key,
            last_execution_time=timestamp,
            created_at=timestamp,
            updated_at=timestamp,
            execution_count=5,
        )
        session.add(state)
        session.commit()
    finally:
        session.close()

    refreshed = manager.list_all_instances()
    refreshed_record = next(
        r for r in refreshed.values() if r.collector_name == "mes.search"
    )

    assert refreshed_record.run_count == 5
    assert refreshed_record.status == "active"
    assert refreshed_record.last_run is not None
    assert refreshed_record.last_run.endswith("+00:00")
