"""Unit tests for observability metrics/logs/timeseries endpoints."""
from unittest.mock import patch

import pytest


class TestListServices:
    def test_discovers_from_up_metric(self):
        from backend.routers import observability as obs

        raw = [
            {"metric": {"service": "payment-api", "kubernetes_namespace": "synthetic"},
             "value": [0, "1"]},
            {"metric": {"service": "auth-service", "kubernetes_namespace": "synthetic"},
             "value": [0, "1"]},
        ]
        with patch.object(obs, "_prom", return_value=raw), \
             patch.object(obs, "_prometheus_reachable", return_value=True):
            result = obs.list_services()

        by_name = {s["name"]: s for s in result["services"]}
        assert by_name["payment-api"]["instances"] == 1
        assert by_name["payment-api"]["status"] == "up"

    def test_fallback_count_by_service_when_up_empty(self):
        from backend.routers import observability as obs

        def prom_side_effect(expr, timeout=10):
            if expr.startswith("up{"):
                return []
            if "count by (service)" in expr and "up{" in expr:
                return [{"metric": {"service": "payment-api"}, "value": [0, "2"]}]
            return []

        with patch.object(obs, "_prom", side_effect=prom_side_effect), \
             patch.object(obs, "_prometheus_reachable", return_value=True):
            result = obs.list_services()

        pay = next(s for s in result["services"] if s["name"] == "payment-api")
        assert pay["instances"] == 2
        assert pay["status"] == "up"

    def test_unknown_when_prometheus_unreachable(self):
        from backend.routers import observability as obs

        with patch.object(obs, "_prom", return_value=[]), \
             patch.object(obs, "_prometheus_reachable", return_value=False):
            result = obs.list_services()

        pay = next(s for s in result["services"] if s["name"] == "payment-api")
        assert pay["instances"] == 0
        assert pay["status"] == "unknown"


class TestGetMetrics:
    def test_core_sli_defaults_to_zero_for_known_service(self):
        from backend.routers import observability as obs

        with patch.object(obs, "_prom", return_value=[]):
            result = obs.get_metrics("payment-api", minutes=10)

        assert result["metrics"]["error_rate"] == 0.0
        assert result["metrics"]["db_errors"] == 0.0
        assert result["metrics"]["pool_exhaustion"] == 0.0

    def test_unknown_service_skips_missing_metrics(self):
        from backend.routers import observability as obs

        with patch.object(obs, "_prom", return_value=[]):
            result = obs.get_metrics("nonexistent-svc", minutes=10)

        assert result["metrics"] == {}

    def test_anomaly_detection_still_works(self):
        from backend.routers import observability as obs

        def prom_side_effect(expr):
            if "http_errors_total" in expr:
                return [{"value": [0, "1.5"]}]
            return []

        with patch.object(obs, "_prom", side_effect=prom_side_effect):
            result = obs.get_metrics("payment-api", minutes=10)

        assert result["metrics"]["error_rate"] == 1.5
        assert any(a["type"] == "HIGH_ERROR_RATE" for a in result["anomalies"])


class TestGetLogs:
    def test_returns_502_with_empty_entries_on_loki_error(self):
        from backend.routers import observability as obs
        from fastapi.responses import JSONResponse

        with patch.object(obs, "_loki", return_value={"error": "timed out"}):
            resp = obs.get_logs("payment-api", minutes=10, limit=50)

        assert isinstance(resp, JSONResponse)
        assert resp.status_code == 502
        body = resp.body.decode()
        assert "timed out" in body
        assert '"entries":[]' in body.replace(" ", "")

    def test_parses_json_log_lines(self):
        from backend.routers import observability as obs

        raw = {
            "data": {
                "result": [{
                    "values": [[
                        "1",
                        '{"ts":"2026-05-25T00:00:00+00:00","level":"ERROR","component":"X","msg":"boom"}',
                    ]],
                }],
            },
        }
        with patch.object(obs, "_loki", return_value=raw):
            result = obs.get_logs("auth-service", minutes=10, limit=50)

        assert result["total"] == 1
        assert result["entries"][0]["level"] == "ERROR"
        assert result["entries"][0]["msg"] == "boom"


class TestGetTimeseries:
    def test_includes_pool_exhaustion_query(self):
        from backend.routers import observability as obs

        assert "pool_exhaustion" in obs._TS_QUERIES
        assert "memory_bytes" in obs._TS_QUERIES
