"""Unit tests for recruiter SQLite analytics (visitor dedup)."""
from pathlib import Path

import pytest

from backend.config import Settings, get_settings
from backend.memory.recruiter_store import (
    RecruiterStore,
    init_recruiter_store,
    maybe_migrate_legacy_recruiter_db,
)


@pytest.fixture
def store(tmp_path):
    return init_recruiter_store(tmp_path / "recruiter.db")


def test_visitor_dedup_same_visitor_two_views(store):
    r1 = store.record_view(session_id="sess-1", visitor_id="visitor-a")
    assert r1.total_views == 1
    assert r1.unique_views == 1
    assert r1.is_new_visitor is True

    r2 = store.record_view(session_id="sess-2", visitor_id="visitor-a")
    assert r2.total_views == 2
    assert r2.unique_views == 1
    assert r2.is_new_visitor is False


def test_visitor_dedup_two_visitors(store):
    store.record_view(visitor_id="visitor-a")
    r = store.record_view(visitor_id="visitor-b")
    assert r.total_views == 2
    assert r.unique_views == 2


def test_session_only_backward_compat(store):
    r1 = store.record_view(session_id="legacy-sess")
    r2 = store.record_view(session_id="legacy-sess")
    assert r1.unique_views == 1
    assert r2.unique_views == 1
    assert r2.total_views == 2


def test_data_dir_resolves_recruiter_db_path():
    s = Settings(data_dir="/data")
    assert s.recruiter_sqlite_path == str(Path("/data") / "recruiter.db")


def test_explicit_recruiter_path_overrides_data_dir():
    s = Settings(data_dir="/data", recruiter_sqlite_path="/custom/recruiter.db")
    assert s.recruiter_sqlite_path == "/custom/recruiter.db"


def test_record_view_stores_country_code(store):
    store.record_view(visitor_id="visitor-us", country_code="us")
    stats = store.get_detailed_stats()
    assert stats["recent_visitors"][0]["country_code"] == "US"


def test_record_view_updates_country_on_return(store):
    store.record_view(visitor_id="visitor-gb", country_code="GB")
    store.record_view(visitor_id="visitor-gb", country_code="GB")
    stats = store.get_detailed_stats()
    assert stats["recent_visitors"][0]["country_code"] == "GB"


def test_record_view_unknown_country_stored_empty(store):
    store.record_view(visitor_id="visitor-unknown")
    stats = store.get_detailed_stats()
    assert stats["recent_visitors"][0]["country_code"] == ""


def test_migrate_legacy_db_when_target_missing(tmp_path, monkeypatch):
    legacy_dir = tmp_path / "legacy" / "data"
    legacy_dir.mkdir(parents=True)
    legacy_db = legacy_dir / "recruiter.db"
    target_db = tmp_path / "data" / "recruiter.db"

    legacy_store = RecruiterStore(legacy_db)
    legacy_store.record_view(visitor_id="v1")
    legacy_store.close()

    monkeypatch.setattr(
        "backend.memory.recruiter_store._DEFAULT_DB",
        legacy_db,
    )

    assert maybe_migrate_legacy_recruiter_db(target_db) is True
    migrated = RecruiterStore(target_db)
    assert migrated.get_stats()["total_views"] == 1
    migrated.close()


def test_migrate_skips_when_target_has_data(tmp_path, monkeypatch):
    legacy_dir = tmp_path / "legacy" / "data"
    legacy_dir.mkdir(parents=True)
    legacy_db = legacy_dir / "recruiter.db"
    target_db = tmp_path / "data" / "recruiter.db"

    legacy_store = RecruiterStore(legacy_db)
    legacy_store.record_view(visitor_id="legacy")
    legacy_store.close()

    target_store = RecruiterStore(target_db)
    target_store.record_view(visitor_id="target-a")
    target_store.record_view(visitor_id="target-b")
    target_store.close()

    monkeypatch.setattr(
        "backend.memory.recruiter_store._DEFAULT_DB",
        legacy_db,
    )

    assert maybe_migrate_legacy_recruiter_db(target_db) is False
    reopened = RecruiterStore(target_db)
    assert reopened.get_stats()["total_views"] == 2
    reopened.close()


def test_init_migrates_legacy_to_data_dir(tmp_path, monkeypatch):
    legacy_dir = tmp_path / "backend" / "data"
    legacy_dir.mkdir(parents=True)
    legacy_db = legacy_dir / "recruiter.db"
    data_dir = tmp_path / "data"
    target_db = data_dir / "recruiter.db"

    legacy_store = RecruiterStore(legacy_db)
    legacy_store.record_view(visitor_id="dev-visitor")
    legacy_store.close()

    monkeypatch.setattr(
        "backend.memory.recruiter_store._DEFAULT_DB",
        legacy_db,
    )
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    get_settings.cache_clear()

    store = init_recruiter_store(target_db)
    assert store.get_stats()["total_views"] == 1
    store.close()
    get_settings.cache_clear()

