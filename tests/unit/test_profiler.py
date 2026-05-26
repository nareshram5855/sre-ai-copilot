"""Unit tests for application profiler endpoints and middleware."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.monitoring import profiler as prof


class TestProfilerSnapshot:
    def test_build_snapshot_has_core_sections(self):
        snap = prof.build_snapshot()
        assert "uptime_seconds" in snap
        assert snap["uptime_seconds"] >= 0
        assert "requests" in snap
        assert "runtime" in snap
        assert "integrations" in snap
        assert "python_version" in snap["runtime"]
        assert "kafka_enabled" in snap["integrations"]

    def test_record_request_updates_stats(self):
        before = prof.build_snapshot()["requests"]["total"]
        prof.record_request(12.5)
        after = prof.build_snapshot()["requests"]["total"]
        assert after == before + 1
        lat = prof.build_snapshot()["requests"]["latency_ms"]
        assert lat["samples"] >= 1

    def test_render_prometheus_includes_counters(self):
        text = prof.render_prometheus()
        assert "sre_ai_uptime_seconds" in text
        assert "sre_ai_requests_total" in text
        assert "sre_ai_kafka_connected" in text
        assert "sre_ai_redis_connected" in text


class TestProfilerEndpoints:
    def test_profiler_returns_200(self, client: TestClient):
        resp = client.get("/api/v1/profiler")
        assert resp.status_code == 200
        body = resp.json()
        assert "requests" in body
        assert "integrations" in body

    def test_profiler_metrics_prometheus_format(self, client: TestClient):
        resp = client.get("/api/v1/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers.get("content-type", "")
        assert "sre_ai_uptime_seconds" in resp.text

    def test_health_exposes_kafka_redis(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        for key in (
            "kafka_enabled",
            "kafka_connected",
            "redis_enabled",
            "redis_connected",
            "session_backend",
        ):
            assert key in body

    def test_events_health_exposes_redis(self, client: TestClient):
        resp = client.get("/api/v1/events/health")
        assert resp.status_code == 200
        body = resp.json()
        assert "redis_enabled" in body
        assert "redis_connected" in body
        assert "kafka_connected" in body

    def test_profiler_middleware_counts_requests(self, client: TestClient):
        before = client.get("/api/v1/profiler").json()["requests"]["total"]
        client.get("/health")
        after = client.get("/api/v1/profiler").json()["requests"]["total"]
        assert after > before


class TestIntegrationStatus:
    def test_graceful_when_redis_kafka_disabled(self, monkeypatch):
        monkeypatch.setenv("REDIS_ENABLED", "false")
        monkeypatch.setenv("KAFKA_ENABLED", "false")
        from backend.config import get_settings

        get_settings.cache_clear()
        status = prof.get_integration_status()
        assert status["kafka_enabled"] is False
        assert status["kafka_connected"] is False
        assert status["redis_enabled"] is False
        assert status["redis_connected"] is False
        assert status["session_backend"] == "memory"

    def test_redis_connected_when_mock_ping(self):
        from backend.memory.persistence import PersistenceState

        mock_client = type("R", (), {"ping": lambda self: True})()
        state = PersistenceState(redis_available=True, redis_client=mock_client, session_backend="redis")
        with patch("backend.memory.persistence.get_persistence_state", return_value=state):
            status = prof.get_integration_status()
        assert status["redis_connected"] is True
