"""Unit tests for Slack notifier — verifies payload shape, error handling, no-op when unconfigured."""
import pytest
from unittest.mock import patch, MagicMock

from backend.integrations.slack import post_triage_alert, post_rca_complete

_TRIAGE_RESULT = {
    "severity": "P1",
    "confidence": 0.91,
    "reasoning": "CPU saturation causing SSO outage.",
    "suggested_fix": "kubectl rollout restart deployment/siteminder -n ciso",
    "estimated_impact": "all internal users",
    "escalate": True,
    "llm_tier": "local",
}

_RCA_RESULT = {
    "severity": "P1",
    "root_cause": "Stale ConfigMap triggered thundering herd.",
    "detection_gap": "3 minutes",
    "impact": {"duration_minutes": 22, "users_affected": "all internal", "services_affected": ["siteminder"]},
    "action_items": [
        {"action": "Add canary", "owner": "CISO Platform", "priority": "P1", "due": "1 week"}
    ],
}


class TestPostTriageAlert:

    def test_skips_when_webhook_not_configured(self):
        with patch("backend.integrations.slack.get_settings") as mock_cfg:
            mock_cfg.return_value.slack_webhook_url = ""
            result = post_triage_alert("TestAlert", _TRIAGE_RESULT)
        assert result is False

    def test_returns_true_on_success(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None

        with patch("backend.integrations.slack.get_settings") as mock_cfg, \
             patch("backend.integrations.slack.httpx.post", return_value=mock_resp) as mock_post:
            mock_cfg.return_value.slack_webhook_url = "https://hooks.slack.com/fake"
            result = post_triage_alert("KubePodCrashLooping", _TRIAGE_RESULT)

        assert result is True
        mock_post.assert_called_once()

    def test_payload_contains_alert_name(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        captured = {}

        with patch("backend.integrations.slack.get_settings") as mock_cfg, \
             patch("backend.integrations.slack.httpx.post", return_value=mock_resp) as mock_post:
            mock_cfg.return_value.slack_webhook_url = "https://hooks.slack.com/fake"
            post_triage_alert("MyAlert", _TRIAGE_RESULT)
            captured = mock_post.call_args.kwargs.get("json", mock_post.call_args[1].get("json", {}))

        payload_str = str(captured)
        assert "MyAlert" in payload_str

    def test_escalation_block_added_for_p1(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None

        with patch("backend.integrations.slack.get_settings") as mock_cfg, \
             patch("backend.integrations.slack.httpx.post", return_value=mock_resp) as mock_post:
            mock_cfg.return_value.slack_webhook_url = "https://hooks.slack.com/fake"
            post_triage_alert("Alert", {**_TRIAGE_RESULT, "escalate": True})
            payload = mock_post.call_args[1]["json"]

        blocks_text = str(payload["blocks"])
        assert "Escalation" in blocks_text or "escalate" in blocks_text.lower()

    def test_returns_false_on_http_error(self):
        import httpx as _httpx

        with patch("backend.integrations.slack.get_settings") as mock_cfg, \
             patch("backend.integrations.slack.httpx.post") as mock_post:
            mock_cfg.return_value.slack_webhook_url = "https://hooks.slack.com/fake"
            mock_post.side_effect = _httpx.ConnectError("connection refused")
            result = post_triage_alert("Alert", _TRIAGE_RESULT)

        assert result is False

    def test_returns_false_on_unexpected_exception(self):
        with patch("backend.integrations.slack.get_settings") as mock_cfg, \
             patch("backend.integrations.slack.httpx.post", side_effect=RuntimeError("boom")):
            mock_cfg.return_value.slack_webhook_url = "https://hooks.slack.com/fake"
            result = post_triage_alert("Alert", _TRIAGE_RESULT)

        assert result is False


class TestPostRCAComplete:

    def test_skips_when_webhook_not_configured(self):
        with patch("backend.integrations.slack.get_settings") as mock_cfg:
            mock_cfg.return_value.slack_webhook_url = ""
            result = post_rca_complete("SiteMinder Outage", _RCA_RESULT)
        assert result is False

    def test_returns_true_on_success(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None

        with patch("backend.integrations.slack.get_settings") as mock_cfg, \
             patch("backend.integrations.slack.httpx.post", return_value=mock_resp):
            mock_cfg.return_value.slack_webhook_url = "https://hooks.slack.com/fake"
            result = post_rca_complete("SiteMinder Outage", _RCA_RESULT)

        assert result is True

    def test_action_items_included_in_payload(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None

        with patch("backend.integrations.slack.get_settings") as mock_cfg, \
             patch("backend.integrations.slack.httpx.post", return_value=mock_resp) as mock_post:
            mock_cfg.return_value.slack_webhook_url = "https://hooks.slack.com/fake"
            post_rca_complete("Outage", _RCA_RESULT)
            payload = mock_post.call_args[1]["json"]

        assert "Add canary" in str(payload["blocks"])
