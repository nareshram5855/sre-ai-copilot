"""
Shared fixtures for all tests.

Design principle: mock at the agent boundary, not deep inside LangChain.
Tests verify OUR logic (routing, risk classification, session management),
not LangChain internals or network calls.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.main import app


# ── API client ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ── Canned agent responses ────────────────────────────────────────────────────

@pytest.fixture
def triage_response() -> dict:
    return {
        "severity": "P2",
        "confidence": 0.85,
        "reasoning": "Pod OOMKill with 8 restarts indicates memory limit too low.",
        "suggested_fix": "kubectl set resources deployment ping-identity-auth --limits=memory=1Gi",
        "similar_incidents": ["OOM incident Jan 2024: ping-identity-auth"],
        "escalate": False,
        "estimated_impact": "~200 IAM users affected",
        "llm_tier": "local",
        "complexity": "medium",
    }


@pytest.fixture
def chat_response() -> dict:
    return {
        "answer": "Run `kubectl logs <pod> -n iam --previous` to see crash logs.",
        "sources": ["pod_crashloop.md"],
        "session_id": "test-session",
        "llm_tier": "local",
        "complexity": "low",
    }


@pytest.fixture
def runbook_response() -> dict:
    return {
        "runbook_source": "pod_crashloop.md",
        "runbook_title": "Runbook: Pod CrashLoopBackOff",
        "estimated_time": "10-15 minutes",
        "steps": [
            {"number": 1, "description": "Get pods", "command": "kubectl get pods -n iam",
             "expected_output": "Pod list", "risk_level": "SAFE"},
            {"number": 2, "description": "Increase memory", "command": "kubectl set resources deployment d --limits=memory=1Gi",
             "expected_output": "Deployment updated", "risk_level": "REQUIRES_APPROVAL"},
        ],
        "safe_steps_count": 1,
        "pending_approval": [
            {"number": 2, "description": "Increase memory", "command": "kubectl set resources deployment d --limits=memory=1Gi",
             "expected_output": "Deployment updated", "risk_level": "REQUIRES_APPROVAL"},
        ],
        "similarity_score": 0.92,
        "llm_tier": "local",
    }


@pytest.fixture
def rca_response() -> dict:
    return {
        "title": "SiteMinder CPU Spike",
        "severity": "P1",
        "summary": "CPU saturation caused SSO outage for 22 minutes.",
        "root_cause": "Stale ConfigMap caused thundering herd of re-authentications.",
        "contributing_factors": ["No canary rollout", "Low CPU alert threshold"],
        "impact": {"duration_minutes": 22, "users_affected": "all internal", "services_affected": ["siteminder"]},
        "timeline": [{"time": "10:02", "event": "ConfigMap updated", "actor": "system"}],
        "remediation": "Rolled back ConfigMap, restarted pods.",
        "prevention": ["Add staged rollout", "Lower alert threshold"],
        "action_items": [{"action": "Add canary", "owner": "CISO Platform", "priority": "P1", "due": "1 week"}],
        "detection_gap": "3 minutes — alert threshold was 90%",
        "rca_markdown": "# RCA: SiteMinder CPU Spike\n...",
        "llm_tier": "advanced",
    }


# ── Mocked agent patchers ─────────────────────────────────────────────────────

@pytest.fixture
def mock_triage(triage_response):
    with patch("backend.routers.triage._agent") as m:
        m.execute.return_value = {**triage_response, "_meta": {"agent": "TriageAgent", "duration_seconds": 1.2}}
        yield m


@pytest.fixture
def mock_chat(chat_response):
    with patch("backend.routers.chat._agent") as m:
        m.execute.return_value = {**chat_response, "_meta": {"agent": "ChatAgent", "duration_seconds": 0.8}}
        yield m


@pytest.fixture
def mock_runbook(runbook_response):
    with patch("backend.routers.runbook._agent") as m:
        m.execute.return_value = {**runbook_response, "_meta": {"agent": "RunbookAgent", "duration_seconds": 1.5}}
        yield m


@pytest.fixture
def mock_rca(rca_response):
    with patch("backend.routers.rca._agent") as m:
        m.execute.return_value = {**rca_response, "_meta": {"agent": "RCAAgent", "duration_seconds": 3.1}}
        yield m
