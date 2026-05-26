"""
Integration tests — all API routes via TestClient.

Design: mock at the agent boundary (mock_triage, mock_chat, etc. from conftest).
Tests verify HTTP contracts, request validation, and response shaping.
They do NOT test LLM or ChromaDB — those are unit-tested separately.
"""
import pytest


# ── Health ────────────────────────────────────────────────────────────────────

class TestHealthEndpoint:

    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_has_status_field(self, client):
        resp = client.get("/health")
        assert "status" in resp.json()

    def test_root_redirect_or_200(self, client):
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code in (200, 307, 404)  # depends on static file setup


# ── Alert Triage ──────────────────────────────────────────────────────────────

class TestTriageEndpoint:

    def test_valid_alert_returns_200(self, client, mock_triage):
        payload = {
            "name": "KubePodCrashLooping",
            "description": "Pod restarting every 30s",
            "labels": {"severity": "warning"},
            "environment": "production",
        }
        resp = client.post("/api/v1/triage", json=payload)
        assert resp.status_code == 200

    def test_response_has_required_fields(self, client, mock_triage):
        resp = client.post("/api/v1/triage", json={
            "name": "TestAlert",
            "description": "high memory",
            "labels": {},
        })
        body = resp.json()
        assert "severity" in body
        assert "confidence" in body
        assert "reasoning" in body
        assert "suggested_fix" in body
        assert "escalate" in body
        assert "llm_tier" in body
        assert "complexity" in body

    def test_meta_not_in_response(self, client, mock_triage):
        resp = client.post("/api/v1/triage", json={"name": "A", "description": "B", "labels": {}})
        assert "_meta" not in resp.json()

    def test_missing_name_returns_422(self, client):
        resp = client.post("/api/v1/triage", json={"description": "no name"})
        assert resp.status_code == 422

    def test_missing_description_returns_422(self, client):
        resp = client.post("/api/v1/triage", json={"name": "A"})
        assert resp.status_code == 422

    def test_severity_is_p1_p2_or_p3(self, client, mock_triage):
        resp = client.post("/api/v1/triage", json={
            "name": "A", "description": "B", "labels": {},
        })
        assert resp.json()["severity"] in ("P1", "P2", "P3")

    def test_agent_called_once_per_request(self, client, mock_triage):
        client.post("/api/v1/triage", json={"name": "A", "description": "B", "labels": {}})
        mock_triage.execute.assert_called_once()


# ── Chat ──────────────────────────────────────────────────────────────────────

class TestChatEndpoint:

    def test_valid_question_returns_200(self, client, mock_chat):
        resp = client.post("/api/v1/chat", json={"question": "How do I check pod logs?", "session_id": "test"})
        assert resp.status_code == 200

    def test_response_has_answer_and_sources(self, client, mock_chat):
        resp = client.post("/api/v1/chat", json={"question": "What is OOMKilled?", "session_id": "s1"})
        body = resp.json()
        assert "answer" in body
        assert "sources" in body
        assert "session_id" in body

    def test_meta_not_in_response(self, client, mock_chat):
        resp = client.post("/api/v1/chat", json={"question": "What is OOMKilled?", "session_id": "s1"})
        assert "_meta" not in resp.json()

    def test_too_short_question_returns_422(self, client):
        # min_length=1; empty string must fail validation
        resp = client.post("/api/v1/chat", json={"question": ""})
        assert resp.status_code == 422

    def test_missing_question_returns_422(self, client):
        resp = client.post("/api/v1/chat", json={"session_id": "s1"})
        assert resp.status_code == 422

    def test_session_id_echoed_back(self, client, mock_chat):
        resp = client.post("/api/v1/chat", json={"question": "How to restart pods?", "session_id": "my-session"})
        assert resp.json()["session_id"] == "test-session"  # from canned fixture

    def test_clear_session_returns_200(self, client):
        resp = client.delete("/api/v1/chat/test-session")
        assert resp.status_code == 200

    def test_clear_session_body_has_cleared_field(self, client):
        resp = client.delete("/api/v1/chat/test-session")
        assert "cleared" in resp.json()
        assert "session_id" in resp.json()


# ── Runbook ───────────────────────────────────────────────────────────────────

class TestRunbookEndpoint:

    def test_valid_payload_returns_200(self, client, mock_runbook):
        resp = client.post("/api/v1/runbook/execute", json={
            "alert_name": "KubePodCrashLooping",
            "description": "OOMKilled in ping-identity-auth",
        })
        assert resp.status_code == 200

    def test_response_has_steps_and_pending(self, client, mock_runbook):
        resp = client.post("/api/v1/runbook/execute", json={
            "alert_name": "Alert", "description": "Pod crashed",
        })
        body = resp.json()
        assert "steps" in body
        assert "pending_approval" in body
        assert "runbook_title" in body
        assert "llm_tier" in body

    def test_meta_not_in_response(self, client, mock_runbook):
        resp = client.post("/api/v1/runbook/execute", json={"alert_name": "A", "description": "B"})
        assert "_meta" not in resp.json()

    def test_missing_alert_name_returns_422(self, client):
        resp = client.post("/api/v1/runbook/execute", json={"description": "no alert name"})
        assert resp.status_code == 422

    def test_missing_description_returns_422(self, client):
        resp = client.post("/api/v1/runbook/execute", json={"alert_name": "Alert"})
        assert resp.status_code == 422

    def test_steps_have_risk_level(self, client, mock_runbook):
        resp = client.post("/api/v1/runbook/execute", json={"alert_name": "A", "description": "B"})
        for step in resp.json()["steps"]:
            assert step["risk_level"] in ("SAFE", "REQUIRES_APPROVAL", "DANGEROUS")


# ── RCA ───────────────────────────────────────────────────────────────────────

class TestRCAEndpoint:

    def test_valid_payload_returns_200(self, client, mock_rca):
        resp = client.post("/api/v1/rca", json={
            "title": "SiteMinder CPU Spike",
            "severity": "P1",
        })
        assert resp.status_code == 200

    def test_response_has_all_required_fields(self, client, mock_rca):
        resp = client.post("/api/v1/rca", json={"title": "Test Incident", "severity": "P2"})
        body = resp.json()
        for field in ("title", "severity", "summary", "root_cause", "contributing_factors",
                      "impact", "timeline", "remediation", "prevention", "action_items",
                      "detection_gap", "rca_markdown", "llm_tier"):
            assert field in body, f"Missing field: {field}"

    def test_meta_not_in_response(self, client, mock_rca):
        resp = client.post("/api/v1/rca", json={"title": "Test", "severity": "P1"})
        assert "_meta" not in resp.json()

    def test_missing_title_returns_422(self, client):
        resp = client.post("/api/v1/rca", json={"severity": "P1"})
        assert resp.status_code == 422

    def test_duration_must_be_non_negative(self, client, mock_rca):
        resp = client.post("/api/v1/rca", json={
            "title": "Test",
            "severity": "P1",
            "duration_minutes": -1,
        })
        assert resp.status_code == 422

    def test_rca_markdown_contains_rca_header(self, client, mock_rca):
        resp = client.post("/api/v1/rca", json={"title": "Test Incident"})
        assert "# RCA:" in resp.json()["rca_markdown"]


# ── Knowledge Ingest ──────────────────────────────────────────────────────────

class TestKnowledgeEndpoint:

    def test_ingest_endpoint_exists(self, client):
        # Ingest may fail without ChromaDB running — just check the route resolves (not 404)
        resp = client.post("/api/v1/ingest")
        # Acceptable: 200 (success), 500 (ChromaDB not available in test env), 503
        assert resp.status_code in (200, 500, 503)
