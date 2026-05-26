"""Unit tests for observability watch endpoint."""
from unittest.mock import patch

import pytest


@pytest.fixture
def mock_services():
    return {
        "services": [
            {"name": "auth-service", "namespace": "synthetic", "status": "up", "instances": 2},
            {"name": "order-service", "namespace": "synthetic", "status": "up", "instances": 1},
        ]
    }


@pytest.fixture
def mock_metrics_healthy():
    return {
        "metrics": {"error_rate": 0.01, "request_rate": 5.0},
        "anomalies": [],
    }


@pytest.fixture
def mock_metrics_critical():
    return {
        "metrics": {"error_rate": 1.5, "request_rate": 2.0},
        "anomalies": [
            {"type": "HIGH_ERROR_RATE", "severity": "critical", "label": "1.5000 errors/s"},
        ],
    }


class TestWatchSummary:
    def test_watch_all_healthy(self, mock_services, mock_metrics_healthy):
        from backend.routers import observability as obs

        with patch.object(obs, "list_services", return_value=mock_services), \
             patch.object(obs, "get_metrics", return_value=mock_metrics_healthy):
            result = obs.watch_summary(minutes=10)

        assert result["overall_health"] == "healthy"
        assert result["service_count"] == 2
        assert result["anomaly_count"] == 0
        assert all(s["health"] == "healthy" for s in result["services"])

    def test_watch_detects_critical(self, mock_services, mock_metrics_healthy, mock_metrics_critical):
        from backend.routers import observability as obs

        def metrics_side_effect(service, minutes):
            if service == "auth-service":
                return mock_metrics_critical
            return mock_metrics_healthy

        with patch.object(obs, "list_services", return_value=mock_services), \
             patch.object(obs, "get_metrics", side_effect=metrics_side_effect):
            result = obs.watch_summary(minutes=10)

        assert result["overall_health"] == "critical"
        assert result["anomaly_count"] == 1
        assert result["anomalies"][0]["service"] == "auth-service"
        auth = next(s for s in result["services"] if s["name"] == "auth-service")
        assert auth["health"] == "critical"
        assert auth["anomaly_count"] == 1

    def test_watch_unknown_when_prometheus_unreachable(self, mock_services, mock_metrics_healthy):
        from backend.routers import observability as obs

        with patch.object(obs, "list_services", return_value=mock_services), \
             patch.object(obs, "get_metrics", return_value=mock_metrics_healthy), \
             patch.object(obs, "_prometheus_reachable", return_value=False):
            result = obs.watch_summary(minutes=10)

        assert result["overall_health"] == "unknown"
        assert result["fleet_health_pct"] is None
        assert result["prometheus_reachable"] is False
        assert all(s["health"] == "unknown" for s in result["services"])

    def test_service_health_helper(self):
        from backend.routers.observability import _service_health

        assert _service_health([]) == "healthy"
        assert _service_health([{"severity": "warning"}]) == "warning"
        assert _service_health([{"severity": "critical"}]) == "critical"

    def test_fleet_health_pct_in_watch_response(self, mock_services, mock_metrics_healthy):
        from backend.routers import observability as obs

        with patch.object(obs, "list_services", return_value=mock_services), \
             patch.object(obs, "get_metrics", return_value=mock_metrics_healthy), \
             patch.object(obs, "_prometheus_reachable", return_value=True):
            result = obs.watch_summary(minutes=10)

        assert result["fleet_health_pct"] == 100
        assert result["healthy_count"] == 2


class TestStackHealth:
    def test_stack_marks_prometheus_down_when_unreachable(self):
        from backend.routers import observability as obs

        with patch.object(obs, "_get", return_value={"error": "Connection refused"}):
            result = obs.stack_health()

        prom = next(t for t in result["tools"] if t["name"] == "Prometheus")
        assert prom["status"] == "down"
        assert prom["stats"]["total_targets"] == 0
        assert result["remediation"]["command"] == "make dev-up"

    def test_stack_no_remediation_when_healthy(self):
        from backend.routers import observability as obs

        targets = {
            "data": {
                "activeTargets": [
                    {"health": "up", "labels": {"job": "otel-collector"}},
                ],
            },
        }
        labels = {"data": ["namespace", "service", "trace_id"]}
        svc_vals = {"data": ["auth-service"]}

        def get_side_effect(url, timeout=10):
            if "/targets" in url:
                return targets
            if "/labels" in url and "service" not in url:
                return labels
            if "label/service/values" in url:
                return svc_vals
            if "count(" in url:
                return {"data": {"result": [{"value": [0, "100"]}]}}
            return {}

        with patch.object(obs, "_get", side_effect=get_side_effect), \
             patch.object(obs._HTTP, "get") as mock_http:
            mock_http.return_value.status_code = 200
            result = obs.stack_health()

        assert result["remediation"] is None
        assert next(t for t in result["tools"] if t["name"] == "Prometheus")["status"] == "up"
