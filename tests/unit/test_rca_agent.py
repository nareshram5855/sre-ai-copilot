"""Unit tests for RCAAgent — markdown rendering and run() logic."""
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.documents import Document

from backend.agents.rca_agent import RCAAgent


def _doc(content: str, source: str = "incident.md") -> tuple:
    return (Document(page_content=content, metadata={"source": source}), 0.15)


@pytest.fixture
def agent():
    return RCAAgent()


@pytest.fixture
def payload():
    return {
        "title": "SiteMinder CPU Spike",
        "severity": "P1",
        "environment": "production",
        "affected_services": ["siteminder", "auth-gateway"],
        "duration_minutes": 22,
        "timeline": [
            {"time": "10:02", "event": "ConfigMap updated", "actor": "system"},
            {"time": "10:05", "event": "CPU spike detected", "actor": "system"},
        ],
        "resolution": "Rolled back ConfigMap, restarted affected pods.",
    }


@pytest.fixture
def llm_result():
    return {
        "title": "SiteMinder CPU Spike",
        "severity": "P1",
        "summary": "CPU saturation caused SSO outage for 22 minutes.",
        "root_cause": "Stale ConfigMap triggered thundering herd of re-authentications.",
        "contributing_factors": ["No canary rollout", "Low CPU alert threshold"],
        "impact": {
            "duration_minutes": 22,
            "users_affected": "all internal users",
            "services_affected": ["siteminder"],
        },
        "timeline": [
            {"time": "10:02", "event": "ConfigMap updated", "actor": "system"},
        ],
        "remediation": "Rolled back ConfigMap.",
        "prevention": ["Add staged rollout", "Lower alert threshold"],
        "action_items": [
            {"action": "Add canary", "owner": "CISO Platform", "priority": "P1", "due": "1 week"},
        ],
        "detection_gap": "3 minutes",
    }


class TestRenderMarkdown:

    def test_title_in_output(self, llm_result):
        md = RCAAgent._render_markdown(llm_result)
        assert "# RCA: SiteMinder CPU Spike" in md

    def test_severity_and_duration_in_output(self, llm_result):
        md = RCAAgent._render_markdown(llm_result)
        assert "P1" in md
        assert "22 min" in md

    def test_timeline_table_rendered(self, llm_result):
        md = RCAAgent._render_markdown(llm_result)
        assert "| Time | Actor | Event |" in md
        assert "10:02" in md
        assert "ConfigMap updated" in md

    def test_action_items_table_rendered(self, llm_result):
        md = RCAAgent._render_markdown(llm_result)
        assert "| Action | Owner | Priority | Due |" in md
        assert "Add canary" in md
        assert "CISO Platform" in md

    def test_contributing_factors_as_bullet_list(self, llm_result):
        md = RCAAgent._render_markdown(llm_result)
        assert "- No canary rollout" in md
        assert "- Low CPU alert threshold" in md

    def test_prevention_as_bullet_list(self, llm_result):
        md = RCAAgent._render_markdown(llm_result)
        assert "- Add staged rollout" in md

    def test_empty_timeline_shows_no_timeline_message(self):
        result = {
            "title": "Test", "severity": "P2", "summary": "s", "root_cause": "r",
            "contributing_factors": [], "impact": {"duration_minutes": 0, "users_affected": "", "services_affected": []},
            "timeline": [], "remediation": "", "prevention": [], "action_items": [], "detection_gap": "",
        }
        md = RCAAgent._render_markdown(result)
        assert "No timeline provided" in md

    def test_empty_action_items_shows_no_items_message(self):
        result = {
            "title": "Test", "severity": "P2", "summary": "s", "root_cause": "r",
            "contributing_factors": [], "impact": {"duration_minutes": 0, "users_affected": "", "services_affected": []},
            "timeline": [{"time": "10:00", "event": "test", "actor": "system"}],
            "remediation": "", "prevention": [], "action_items": [], "detection_gap": "",
        }
        md = RCAAgent._render_markdown(result)
        assert "No action items" in md


class TestFormatSimilar:

    def test_empty_returns_no_similar_message(self):
        assert "No similar past incidents" in RCAAgent._format_similar([])

    def test_source_basename_and_similarity_shown(self):
        doc = Document(page_content="OOM spike Jan 2024", metadata={"source": "/data/oom.md"})
        result = RCAAgent._format_similar([(doc, 0.1)])
        assert "oom.md" in result
        assert "sim=0.90" in result

    def test_content_truncated_at_400_chars(self):
        doc = Document(page_content="X" * 1000, metadata={"source": "x.md"})
        result = RCAAgent._format_similar([(doc, 0.1)])
        assert "X" * 401 not in result


class TestFormatTimelineText:

    def test_formats_each_event_on_new_line(self):
        events = [
            {"time": "10:00", "event": "alert fired"},
            {"time": "10:05", "event": "engineer paged"},
        ]
        result = RCAAgent._format_timeline_text(events)
        assert "- 10:00: alert fired" in result
        assert "- 10:05: engineer paged" in result

    def test_missing_time_defaults_to_placeholder(self):
        result = RCAAgent._format_timeline_text([{"event": "something"}])
        assert "??:??" in result

    def test_empty_list_returns_empty_string(self):
        assert RCAAgent._format_timeline_text([]) == ""


class TestRCAAgentRun:

    def _setup_chain(self, mock_prompt, return_value):
        # LCEL builds chain as (_PROMPT | llm) | parser — two levels of __or__
        mock_prompt.__or__.return_value.__or__.return_value.invoke.return_value = return_value

    def test_rca_markdown_included_in_result(self, agent, payload, llm_result):
        with patch.object(agent, "_retrieve", return_value=[_doc("past incident")]), \
             patch("backend.config.get_settings") as mock_cfg, \
             patch("backend.agents.rca_agent.get_llm") as mock_get_llm:

            mock_cfg.return_value.allow_external_llm = False
            mock_cfg.return_value.anthropic_api_key = ""
            mock_get_llm.return_value = MagicMock()

            with patch("backend.agents.rca_agent._PROMPT") as mock_prompt:
                self._setup_chain(mock_prompt, dict(llm_result))
                result = agent.run(payload)

        assert "rca_markdown" in result
        assert "# RCA:" in result["rca_markdown"]

    def test_uses_local_tier_when_external_disabled(self, agent, payload, llm_result):
        with patch.object(agent, "_retrieve", return_value=[]), \
             patch("backend.config.get_settings") as mock_cfg, \
             patch("backend.agents.rca_agent.get_llm") as mock_get_llm:

            mock_cfg.return_value.allow_external_llm = False
            mock_cfg.return_value.anthropic_api_key = ""
            mock_get_llm.return_value = MagicMock()

            with patch("backend.agents.rca_agent._PROMPT") as mock_prompt:
                self._setup_chain(mock_prompt, dict(llm_result))
                result = agent.run(payload)

        assert result["llm_tier"] == "local"

    def test_uses_advanced_tier_when_external_enabled_with_key(self, agent, payload, llm_result):
        with patch.object(agent, "_retrieve", return_value=[]), \
             patch("backend.config.get_settings") as mock_cfg, \
             patch("backend.agents.rca_agent.get_llm") as mock_get_llm:

            mock_cfg.return_value.allow_external_llm = True
            mock_cfg.return_value.anthropic_api_key = "sk-ant-fake-key"
            mock_get_llm.return_value = MagicMock()

            with patch("backend.agents.rca_agent._PROMPT") as mock_prompt:
                self._setup_chain(mock_prompt, dict(llm_result))
                result = agent.run(payload)

        assert result["llm_tier"] == "advanced"

    def test_payload_sanitized_before_llm_call(self, agent, llm_result):
        sensitive_payload = {
            "title": "Auth failure",
            "severity": "P1",
            "environment": "production",
            "affected_services": [],
            "duration_minutes": 5,
            "timeline": [],
            "resolution": "password=supersecret123 was rotated",
        }
        captured = {}

        def capture_invoke(args):
            captured.update(args)
            return dict(llm_result)

        with patch.object(agent, "_retrieve", return_value=[]), \
             patch("backend.config.get_settings") as mock_cfg, \
             patch("backend.agents.rca_agent.get_llm") as mock_get_llm:

            mock_cfg.return_value.allow_external_llm = False
            mock_cfg.return_value.anthropic_api_key = ""
            mock_get_llm.return_value = MagicMock()

            with patch("backend.agents.rca_agent._PROMPT") as mock_prompt:
                mock_prompt.__or__.return_value.__or__.return_value.invoke.side_effect = capture_invoke
                agent.run(sensitive_payload)

        assert "supersecret123" not in captured.get("resolution", "")
