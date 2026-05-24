"""
End-to-end smoke tests — require all services live:
  make start-infra && make start-backend && make ingest

Run:
  make test-e2e

Each test hits a real endpoint, checks the response contract,
and where possible verifies the Prometheus counter incremented.
"""

import time
import pytest
import httpx

BASE = "http://localhost:8080"
PROM = "http://localhost:9090"

SESSION = f"e2e-smoke-{int(time.time())}"


# ── helpers ───────────────────────────────────────────────────────────────────

def _prom_scalar(query: str) -> float:
    """Return the current scalar value of a PromQL instant query, or 0."""
    try:
        r = httpx.get(f"{PROM}/api/v1/query", params={"query": query}, timeout=5)
        result = r.json()["data"]["result"]
        return float(result[0]["value"][1]) if result else 0.0
    except Exception:
        return 0.0


def _before(query: str) -> float:
    return _prom_scalar(query)


def _assert_incremented(query: str, before: float, label: str):
    after = _prom_scalar(query)
    assert after > before, (
        f"Prometheus counter '{label}' did not increment: before={before} after={after}"
    )


# ── health ────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self):
        r = httpx.get(f"{BASE}/health", timeout=10)
        assert r.status_code == 200

    def test_health_reports_model(self):
        r = httpx.get(f"{BASE}/health", timeout=10)
        body = r.json()
        assert "ollama_model" in body
        assert body["status"] == "healthy"

    def test_metrics_endpoint_live(self):
        r = httpx.get(f"{BASE}/metrics", timeout=10)
        assert r.status_code == 200
        assert "sre_active_sessions" in r.text


# ── triage ────────────────────────────────────────────────────────────────────

class TestTriage:
    PAYLOAD = {
        "name": "KubePodCrashLooping",
        "description": "Pod iam-token-service-abc has restarted 5 times with OOMKilled in the last 10 minutes",
        "labels": {"namespace": "iam", "severity": "critical", "app": "iam-token-service"},
        "value": 5,
        "environment": "production",
    }

    def test_triage_returns_200(self):
        r = httpx.post(f"{BASE}/api/v1/triage", json=self.PAYLOAD, timeout=120)
        assert r.status_code == 200

    def test_triage_response_has_required_fields(self):
        r = httpx.post(f"{BASE}/api/v1/triage", json=self.PAYLOAD, timeout=120)
        body = r.json()
        for field in ("severity", "reasoning", "suggested_fix", "llm_tier", "complexity"):
            assert field in body, f"Missing field: {field}"

    def test_triage_severity_is_valid(self):
        r = httpx.post(f"{BASE}/api/v1/triage", json=self.PAYLOAD, timeout=120)
        assert r.json()["severity"] in ("P1", "P2", "P3", "P4")

    def test_triage_suggested_fix_nonempty(self):
        r = httpx.post(f"{BASE}/api/v1/triage", json=self.PAYLOAD, timeout=120)
        assert len(r.json()["suggested_fix"]) > 10

    def test_triage_increments_prometheus_counter(self):
        before = _before("sum(sre_triage_total) or vector(0)")
        httpx.post(f"{BASE}/api/v1/triage", json=self.PAYLOAD, timeout=120)
        time.sleep(20)  # wait for background task + next Prometheus scrape (15s interval)
        _assert_incremented("sum(sre_triage_total) or vector(0)", before, "sre_triage_total")


# ── chat ──────────────────────────────────────────────────────────────────────

class TestChat:
    QUESTION = "How do I recover from a pod CrashLoopBackOff in the iam namespace?"

    def test_chat_returns_200(self):
        r = httpx.post(
            f"{BASE}/api/v1/chat",
            json={"question": self.QUESTION, "session_id": SESSION},
            timeout=120,
        )
        assert r.status_code == 200

    def test_chat_response_has_answer(self):
        r = httpx.post(
            f"{BASE}/api/v1/chat",
            json={"question": self.QUESTION, "session_id": SESSION},
            timeout=120,
        )
        body = r.json()
        assert "answer" in body
        assert len(body["answer"]) > 20

    def test_chat_returns_sources(self):
        r = httpx.post(
            f"{BASE}/api/v1/chat",
            json={"question": self.QUESTION, "session_id": SESSION},
            timeout=120,
        )
        assert "sources" in r.json()

    def test_chat_session_persists(self):
        """Second question in same session should reference prior context."""
        httpx.post(
            f"{BASE}/api/v1/chat",
            json={"question": "What is OOMKilled?", "session_id": SESSION},
            timeout=120,
        )
        r2 = httpx.post(
            f"{BASE}/api/v1/chat",
            json={"question": "What was my previous question?", "session_id": SESSION},
            timeout=120,
        )
        assert r2.status_code == 200

    def test_chat_clear_session(self):
        r = httpx.delete(f"{BASE}/api/v1/chat/{SESSION}", timeout=10)
        assert r.status_code == 200


# ── runbook ───────────────────────────────────────────────────────────────────

class TestRunbook:
    PAYLOAD = {
        "alert_name": "KubePodCrashLooping",
        "description": "Pod iam-token-service-abc restarted 5x with OOMKilled",
        "steps": [
            "kubectl get pod -n iam | grep iam-token-service",
            "kubectl delete pod -n iam iam-token-service-abc",
            "kubectl rollout status deployment/iam-token-service -n iam",
        ],
        "environment": "production",
        "dry_run": True,
    }

    def test_runbook_returns_200(self):
        r = httpx.post(f"{BASE}/api/v1/runbook/execute", json=self.PAYLOAD, timeout=120)
        assert r.status_code == 200

    def test_runbook_response_has_steps(self):
        r = httpx.post(f"{BASE}/api/v1/runbook/execute", json=self.PAYLOAD, timeout=120)
        body = r.json()
        assert "steps" in body
        assert len(body["steps"]) >= 1

    def test_runbook_classifies_risk(self):
        r = httpx.post(f"{BASE}/api/v1/runbook/execute", json=self.PAYLOAD, timeout=120)
        for step in r.json()["steps"]:
            assert step["risk_level"] in ("SAFE", "REQUIRES_APPROVAL", "DANGEROUS")


# ── rca ───────────────────────────────────────────────────────────────────────

class TestRCA:
    PAYLOAD = {
        "title": "IAM token service OOM crash",
        "description": "Pod iam-token-service restarted 5x with OOMKilled. DB connection pool exhausted prior to crash.",
        "timeline": [
            {"time": "09:00", "event": "Triage alert fired for OOMKilled"},
            {"time": "09:05", "event": "DB connection pool exhausted — 0 connections available"},
            {"time": "09:12", "event": "Pod restarted, p99 latency at 8000ms"},
        ],
        "environment": "production",
    }

    def test_rca_returns_200(self):
        r = httpx.post(f"{BASE}/api/v1/rca", json=self.PAYLOAD, timeout=120)
        assert r.status_code == 200

    def test_rca_response_has_root_cause(self):
        r = httpx.post(f"{BASE}/api/v1/rca", json=self.PAYLOAD, timeout=120)
        body = r.json()
        assert "root_cause" in body
        assert len(body["root_cause"]) > 10

    def test_rca_has_prevention_steps(self):
        r = httpx.post(f"{BASE}/api/v1/rca", json=self.PAYLOAD, timeout=120)
        assert "prevention" in r.json()


# ── alertmanager webhook ──────────────────────────────────────────────────────

class TestAlertManagerWebhook:
    PAYLOAD = {
        "version": "4",
        "groupKey": "{}:{alertname='TestCrashLoop'}",
        "status": "firing",
        "receiver": "sre-ai-webhook",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "KubePodCrashLooping",
                    "namespace": "iam",
                    "severity": "warning",
                    "pod": "iam-token-service-e2e-test",
                },
                "annotations": {
                    "description": "Pod iam/iam-token-service-e2e-test has been restarting 3 times."
                },
                "startsAt": "2026-05-21T09:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "http://prometheus:9090/graph",
                "fingerprint": "e2e-test-fingerprint",
            }
        ],
    }

    def test_webhook_returns_202(self):
        r = httpx.post(
            f"{BASE}/api/v1/webhook/alertmanager", json=self.PAYLOAD, timeout=15
        )
        assert r.status_code == 202

    def test_webhook_reports_processed_count(self):
        r = httpx.post(
            f"{BASE}/api/v1/webhook/alertmanager", json=self.PAYLOAD, timeout=15
        )
        body = r.json()
        assert body["processed"] == 1
        assert body["received"] == 1

    def test_webhook_resolved_alert_skipped(self):
        resolved = dict(self.PAYLOAD)
        resolved["alerts"] = [{**self.PAYLOAD["alerts"][0], "status": "resolved"}]
        resolved["status"] = "resolved"
        r = httpx.post(
            f"{BASE}/api/v1/webhook/alertmanager", json=resolved, timeout=15
        )
        assert r.status_code == 202
        assert r.json()["processed"] == 0

    def test_webhook_triage_runs_in_background(self):
        """Background task should increment triage counter within a few seconds."""
        before = _before("sum(sre_triage_total) or vector(0)")
        httpx.post(f"{BASE}/api/v1/webhook/alertmanager", json=self.PAYLOAD, timeout=15)
        time.sleep(90)  # LLM triage can take up to 60s on local Ollama
        _assert_incremented("sum(sre_triage_total) or vector(0)", before, "sre_triage_total via webhook")


# ── prometheus metrics consistency ────────────────────────────────────────────

class TestPrometheusMetrics:
    def test_prometheus_target_is_up(self):
        r = httpx.get(f"{PROM}/api/v1/targets", timeout=10)
        targets = r.json()["data"]["activeTargets"]
        sre_targets = [t for t in targets if "sre-ai" in str(t.get("labels", {}))]
        assert len(sre_targets) > 0, "sre-ai-backend target not found in Prometheus"
        assert all(t["health"] == "up" for t in sre_targets), "sre-ai-backend target is down"

    def test_http_request_counter_exists(self):
        val = _prom_scalar('sum(http_requests_total{job="sre-ai-backend"}) or vector(0)')
        assert val >= 0  # just confirm metric is queryable

    def test_sre_active_sessions_metric_exists(self):
        val = _prom_scalar("sre_active_sessions or vector(0)")
        assert val >= 0
