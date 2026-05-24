"""Unit tests for Prometheus metrics helpers."""
import pytest
from unittest.mock import patch, MagicMock

from backend.integrations.metrics import record_agent_run, record_triage, record_slack


class TestRecordAgentRun:

    def test_records_duration_histogram(self):
        with patch("backend.integrations.metrics.AGENT_DURATION") as mock_hist, \
             patch("backend.integrations.metrics.LLM_TIER_COUNTER"), \
             patch("backend.integrations.metrics.AGENT_ERROR_COUNTER"):
            record_agent_run("TriageAgent", tier="local", complexity="low", duration=1.23)
            mock_hist.labels.assert_called_once_with(agent="TriageAgent", tier="local", complexity="low")
            mock_hist.labels.return_value.observe.assert_called_once_with(1.23)

    def test_records_tier_counter(self):
        with patch("backend.integrations.metrics.AGENT_DURATION"), \
             patch("backend.integrations.metrics.LLM_TIER_COUNTER") as mock_counter, \
             patch("backend.integrations.metrics.AGENT_ERROR_COUNTER"):
            record_agent_run("ChatAgent", tier="standard", complexity="medium", duration=0.5)
            mock_counter.labels.assert_called_once_with(tier="standard", complexity="medium")
            mock_counter.labels.return_value.inc.assert_called_once()

    def test_increments_error_counter_on_failure(self):
        with patch("backend.integrations.metrics.AGENT_DURATION"), \
             patch("backend.integrations.metrics.LLM_TIER_COUNTER"), \
             patch("backend.integrations.metrics.AGENT_ERROR_COUNTER") as mock_err:
            record_agent_run("RCAAgent", tier="local", complexity="critical", duration=3.0, error=True)
            mock_err.labels.assert_called_once_with(agent="RCAAgent")
            mock_err.labels.return_value.inc.assert_called_once()

    def test_no_error_counter_on_success(self):
        with patch("backend.integrations.metrics.AGENT_DURATION"), \
             patch("backend.integrations.metrics.LLM_TIER_COUNTER"), \
             patch("backend.integrations.metrics.AGENT_ERROR_COUNTER") as mock_err:
            record_agent_run("TriageAgent", tier="local", complexity="low", duration=0.5, error=False)
            mock_err.labels.return_value.inc.assert_not_called()


class TestRecordTriage:

    def test_labels_severity_tier_escalated(self):
        with patch("backend.integrations.metrics.TRIAGE_COUNTER") as mock_counter:
            record_triage(severity="P1", tier="premium", escalated=True)
            mock_counter.labels.assert_called_once_with(severity="P1", tier="premium", escalated="true")
            mock_counter.labels.return_value.inc.assert_called_once()

    def test_escalated_false_stringified(self):
        with patch("backend.integrations.metrics.TRIAGE_COUNTER") as mock_counter:
            record_triage(severity="P3", tier="local", escalated=False)
            call_kwargs = mock_counter.labels.call_args[1]
            assert call_kwargs["escalated"] == "false"


class TestRecordSlack:

    def test_success_label(self):
        with patch("backend.integrations.metrics.SLACK_NOTIFICATION_COUNTER") as mock_counter:
            record_slack("triage", success=True)
            mock_counter.labels.assert_called_once_with(type="triage", success="true")

    def test_failure_label(self):
        with patch("backend.integrations.metrics.SLACK_NOTIFICATION_COUNTER") as mock_counter:
            record_slack("rca", success=False)
            call_kwargs = mock_counter.labels.call_args[1]
            assert call_kwargs["success"] == "false"
