"""Integration tests for AlertManager webhook endpoint."""
import pytest
from unittest.mock import patch, MagicMock


_FIRING_PAYLOAD = {
    "version": "4",
    "groupKey": "{}:{alertname='KubePodCrashLooping'}",
    "status": "firing",
    "receiver": "sre-ai-copilot",
    "alerts": [
        {
            "status": "firing",
            "labels": {
                "alertname": "KubePodCrashLooping",
                "severity": "warning",
                "namespace": "iam",
                "env": "production",
            },
            "annotations": {
                "summary": "Pod is crash looping",
                "description": "Pod ping-identity-auth restarting every 30s with OOMKilled",
            },
            "startsAt": "2024-01-15T10:02:00Z",
            "fingerprint": "abc123",
        }
    ],
}

_RESOLVED_PAYLOAD = {
    "version": "4",
    "status": "resolved",
    "receiver": "sre-ai-copilot",
    "alerts": [
        {
            "status": "resolved",
            "labels": {"alertname": "KubePodCrashLooping"},
            "annotations": {},
            "startsAt": "2024-01-15T10:02:00Z",
            "fingerprint": "abc123",
        }
    ],
}


class TestAlertManagerWebhook:

    def test_firing_alert_returns_202(self, client):
        with patch("backend.routers.alertmanager._agent") as mock_agent:
            mock_agent.execute.return_value = {
                "severity": "P2", "confidence": 0.8, "reasoning": "test",
                "suggested_fix": "restart", "similar_incidents": [], "escalate": False,
                "estimated_impact": "low", "llm_tier": "local", "complexity": "low",
                "_meta": {"agent": "TriageAgent", "duration_seconds": 1.0},
            }
            resp = client.post("/api/v1/webhook/alertmanager", json=_FIRING_PAYLOAD)

        assert resp.status_code == 202

    def test_firing_alert_response_shape(self, client):
        with patch("backend.routers.alertmanager._agent") as mock_agent:
            mock_agent.execute.return_value = {
                "severity": "P2", "confidence": 0.8, "reasoning": "test",
                "suggested_fix": "restart", "similar_incidents": [], "escalate": False,
                "estimated_impact": "low", "llm_tier": "local", "complexity": "low",
                "_meta": {"agent": "TriageAgent", "duration_seconds": 1.0},
            }
            resp = client.post("/api/v1/webhook/alertmanager", json=_FIRING_PAYLOAD)

        body = resp.json()
        assert body["received"] == 1
        assert body["processed"] == 1
        assert body["skipped"] == 0

    def test_resolved_alerts_skipped(self, client):
        resp = client.post("/api/v1/webhook/alertmanager", json=_RESOLVED_PAYLOAD)
        assert resp.status_code == 202
        body = resp.json()
        assert body["processed"] == 0
        assert body["skipped"] == 1

    def test_empty_alerts_returns_202(self, client):
        payload = {**_FIRING_PAYLOAD, "alerts": []}
        resp = client.post("/api/v1/webhook/alertmanager", json=payload)
        assert resp.status_code == 202
        assert resp.json()["received"] == 0

    def test_multiple_alerts_all_processed(self, client):
        alert = _FIRING_PAYLOAD["alerts"][0]
        payload = {
            **_FIRING_PAYLOAD,
            "alerts": [alert, {**alert, "fingerprint": "def456"}],
        }
        with patch("backend.routers.alertmanager._agent") as mock_agent:
            mock_agent.execute.return_value = {
                "severity": "P2", "confidence": 0.8, "reasoning": "test",
                "suggested_fix": "restart", "similar_incidents": [], "escalate": False,
                "estimated_impact": "low", "llm_tier": "local", "complexity": "low",
                "_meta": {"agent": "TriageAgent", "duration_seconds": 1.0},
            }
            resp = client.post("/api/v1/webhook/alertmanager", json=payload)

        body = resp.json()
        assert body["received"] == 2
        assert body["processed"] == 2

    def test_missing_alert_name_uses_default(self, client):
        payload = {
            **_FIRING_PAYLOAD,
            "alerts": [{
                "status": "firing",
                "labels": {"severity": "warning"},  # no alertname
                "annotations": {"description": "something happened"},
                "startsAt": "2024-01-15T10:02:00Z",
                "fingerprint": "xyz",
            }],
        }
        with patch("backend.routers.alertmanager._agent") as mock_agent:
            mock_agent.execute.return_value = {
                "severity": "P2", "confidence": 0.7, "reasoning": "test",
                "suggested_fix": "", "similar_incidents": [], "escalate": False,
                "estimated_impact": "unknown", "llm_tier": "local", "complexity": "low",
                "_meta": {"agent": "TriageAgent", "duration_seconds": 1.0},
            }
            resp = client.post("/api/v1/webhook/alertmanager", json=payload)

        assert resp.status_code == 202
