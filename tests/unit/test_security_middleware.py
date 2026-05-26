"""Unit tests for the API-key middleware and integration helpers.

Focus:
  * Dev-mode bypass when API_KEY is unset
  * 401 when API_KEY is set and request is missing or wrong key
  * 200 when X-API-Key header or Bearer token matches
  * Stable PagerDuty dedup keys
  * ServiceNow / PagerDuty `is_configured` returns False when env is empty
"""
import os
from unittest.mock import patch


# ── _security.require_api_key ─────────────────────────────────────────────────

def test_resolve_endpoint_bypassed_when_api_key_unset(client):
    """No API_KEY → unauthenticated requests succeed (dev mode)."""
    with patch.dict(os.environ, {"API_KEY": ""}, clear=False):
        resp = client.post(
            "/api/v1/incidents/test:demo/resolve",
            json={"outcome": "resolved", "alert_name": "Test", "namespace": "demo"},
        )
    # Bypass means request reaches the handler. Handler may return 200 or 500
    # depending on ChromaDB availability, but never 401.
    assert resp.status_code != 401


def test_resolve_rejects_missing_key_when_set(client):
    """API_KEY set + no header → 401."""
    with patch.dict(os.environ, {"API_KEY": "test-secret-123"}, clear=False):
        resp = client.post(
            "/api/v1/incidents/test:demo/resolve",
            json={"outcome": "resolved", "alert_name": "Test", "namespace": "demo"},
        )
    assert resp.status_code == 401
    assert "API key" in resp.json()["detail"]


def test_resolve_accepts_valid_x_api_key(client):
    """X-API-Key header with the correct value bypasses 401."""
    with patch.dict(os.environ, {"API_KEY": "test-secret-123"}, clear=False):
        resp = client.post(
            "/api/v1/incidents/test:demo/resolve",
            headers={"X-API-Key": "test-secret-123"},
            json={"outcome": "resolved", "alert_name": "Test", "namespace": "demo"},
        )
    assert resp.status_code != 401


def test_resolve_accepts_valid_bearer(client):
    with patch.dict(os.environ, {"API_KEY": "test-secret-123"}, clear=False):
        resp = client.post(
            "/api/v1/incidents/test:demo/resolve",
            headers={"Authorization": "Bearer test-secret-123"},
            json={"outcome": "resolved", "alert_name": "Test", "namespace": "demo"},
        )
    assert resp.status_code != 401


# ── system endpoints (used by the frontend write-action UI) ──────────────────

def test_system_actions_endpoint_returns_registries(client):
    resp = client.get("/api/v1/incidents/system/actions")
    assert resp.status_code == 200
    body = resp.json()
    assert "write_actions" in body and "read_actions" in body
    # Sanity: read actions and write actions are disjoint.
    assert not (set(body["read_actions"]) & set(body["write_actions"]))


def test_system_integrations_endpoint_returns_booleans(client):
    """Shape contract: frontend uses these flags to decide what badges to render."""
    resp = client.get("/api/v1/incidents/system/integrations")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) >= {"servicenow", "pagerduty"}
    assert isinstance(body["servicenow"], bool)
    assert isinstance(body["pagerduty"], bool)


# ── PagerDuty + ServiceNow client helpers ────────────────────────────────────

def test_pagerduty_dedup_key_stable_across_calls():
    from backend.integrations import pagerduty

    a = pagerduty.dedup_key_for("HighCpu", "iam")
    b = pagerduty.dedup_key_for("HighCpu", "iam")
    assert a == b == "sre-ai:HighCpu:iam"
    # Empty namespace fallback should still be deterministic.
    assert pagerduty.dedup_key_for("HighCpu", "") == "sre-ai:HighCpu:unknown"


def test_pagerduty_is_configured_false_when_routing_key_empty():
    from backend.integrations import pagerduty

    fake_cfg = type("Cfg", (), {"pagerduty_routing_key": ""})()
    with patch.object(pagerduty, "get_settings", lambda: fake_cfg):
        assert pagerduty.is_configured() is False


def test_servicenow_is_configured_false_when_url_empty():
    from backend.integrations import servicenow

    fake_cfg = type("Cfg", (), {
        "servicenow_url": "",
        "servicenow_user": "",
        "servicenow_password": "",
    })()
    with patch.object(servicenow, "get_settings", lambda: fake_cfg):
        assert servicenow.is_configured() is False
