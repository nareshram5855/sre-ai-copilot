"""Unit tests for Redis/in-memory persistence stores."""
import json
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from backend.memory.audit_store import ExecutionAuditStore, init_audit_store, log_execution_audit, sanitize_details
from backend.memory.dedup_store import (
    InMemoryAnomalyFingerprintStore,
    InMemoryTriageDedupStore,
    RedisAnomalyFingerprintStore,
    RedisTriageDedupStore,
)
from backend.memory.persistence import init_persistence
from backend.memory.redis_store import RedisSessionStore
from backend.memory.session_store import InMemorySessionStore
from backend.routers.alertmanager import RecentTriage


class TestInMemorySessionStore:
    def test_add_and_get_history(self):
        store = InMemorySessionStore(max_history=5)
        store.add_exchange("s1", "hello", "hi there")
        history = store.get_history("s1")
        assert len(history) == 2
        assert isinstance(history[0], HumanMessage)
        assert isinstance(history[1], AIMessage)


class TestRedisSessionStoreWithMock:
    def test_get_history_deserializes_messages(self):
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.lrange.return_value = [
            json.dumps({"type": "human", "content": "q"}),
            json.dumps({"type": "ai", "content": "a"}),
        ]
        with patch("redis.Redis", return_value=mock_redis):
            store = RedisSessionStore(host="localhost", port=6379)
        history = store.get_history("sess-1")
        assert len(history) == 2
        assert history[0].content == "q"

    def test_add_exchange_pipeline(self):
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        pipe = MagicMock()
        mock_redis.pipeline.return_value = pipe
        with patch("redis.Redis", return_value=mock_redis):
            store = RedisSessionStore(host="localhost", port=6379)
        store.add_exchange("sess-2", "question", "answer")
        pipe.rpush.assert_called()
        pipe.execute.assert_called_once()


class TestDedupStores:
    def test_in_memory_anomaly_fingerprints(self):
        store = InMemoryAnomalyFingerprintStore()
        fp = frozenset({"a:1"})
        store.set_fingerprints(fp)
        assert store.get_fingerprints() == fp
        store.reset()
        assert store.get_fingerprints() == frozenset()

    def test_in_memory_triage_dedup_fire_count(self):
        store = InMemoryTriageDedupStore()
        key = ("AlertA", "demo")
        entry = RecentTriage(
            alert_name="AlertA",
            severity="P2",
            summary="s",
            suggested_fix="f",
            namespace="demo",
            pod="p",
            triaged_at="2026-01-01T00:00:00+00:00",
            escalate=False,
            llm_tier="local",
            fire_count=1,
        )
        store.upsert(key, entry)
        entry2 = entry.model_copy(update={"fire_count": 2})
        store.upsert(key, entry2)
        assert store.get_fire_count("AlertA", "demo") == 2
        assert len(store.list_recent()) == 1

    def test_redis_triage_dedup_uses_mock(self):
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = MagicMock()
        store = RedisTriageDedupStore(mock_redis)
        entry = RecentTriage(
            alert_name="AlertB",
            severity="P1",
            summary="s",
            suggested_fix="f",
            namespace="ns",
            pod="p",
            triaged_at="2026-01-01T00:00:00+00:00",
            escalate=True,
            llm_tier="local",
            fire_count=3,
        )
        store.upsert(("AlertB", "ns"), entry)
        mock_redis.pipeline.return_value.execute.assert_called_once()

    def test_redis_anomaly_fingerprint_set(self):
        mock_redis = MagicMock()
        pipe = MagicMock()
        mock_redis.pipeline.return_value = pipe
        store = RedisAnomalyFingerprintStore(mock_redis)
        store.set_fingerprints(frozenset({"x:y"}))
        pipe.sadd.assert_called_once()
        pipe.execute.assert_called_once()


class TestPersistenceFallback:
    def test_init_without_redis_uses_memory(self, tmp_path, monkeypatch):
        monkeypatch.setenv("REDIS_ENABLED", "false")
        monkeypatch.setenv("CHECKPOINT_SQLITE_PATH", str(tmp_path / "cp.db"))
        monkeypatch.setenv("AUDIT_SQLITE_PATH", str(tmp_path / "audit.db"))
        from backend.config import get_settings

        get_settings.cache_clear()
        state = init_persistence()
        assert state.session_backend == "memory"
        assert state.dedup_backend == "memory"
        assert state.redis_available is False


class TestAuditStore:
    def test_append_and_list(self, tmp_path):
        db = tmp_path / "audit.db"
        store = ExecutionAuditStore(db)
        from backend.memory.audit_store import AuditEntry

        store.append(
            AuditEntry(
                timestamp="2026-01-01T00:00:00+00:00",
                execution_id="exec-1",
                action_type="tool_read",
                status="success",
                tool_name="get_pods",
                command_details='{"namespace":"demo"}',
            )
        )
        rows = store.list_entries(limit=10, execution_id="exec-1")
        assert len(rows) == 1
        assert rows[0]["tool_name"] == "get_pods"
        store.close()

    def test_sanitize_details_redacts_credentials(self):
        text = sanitize_details({"cmd": "kubectl --token=secret123 get pods"})
        assert "secret123" not in text
        assert "REDACTED" in text

    def test_log_execution_audit_no_store_is_noop(self):
        import backend.memory.audit_store as mod

        mod._audit_store = None
        log_execution_audit(execution_id="x", action_type="test", status="ok")

    def test_log_execution_audit_writes(self, tmp_path):
        init_audit_store(tmp_path / "audit.db")
        log_execution_audit(
            execution_id="exec-99",
            action_type="execution_start",
            status="started",
            command_details={"alert": "OOM"},
        )
        store = init_audit_store(tmp_path / "audit.db")
        entries = store.list_entries(execution_id="exec-99")
        assert entries
        assert entries[0]["action_type"] == "execution_start"
