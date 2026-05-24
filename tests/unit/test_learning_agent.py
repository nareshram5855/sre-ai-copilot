"""Unit tests for LearningAgent."""
import pytest
from unittest.mock import patch

from backend.agents.learning_agent import LearningAgent


@pytest.fixture
def agent():
    return LearningAgent()


RESOLVED_PAYLOAD = {
    "alert_name": "JavaPodOOMKilled",
    "namespace": "demo",
    "outcome": "resolved",
    "final_summary": "Increased memory limit to 256Mi",
    "triage_summary": "Pod OOMKilled in demo namespace",
    "scratchpad": [
        {"action": "kubectl_patch", "args": {"deployment": "oom-demo"}, "observation": "patched ok"},
        {"action": "kubectl_rollout_status", "args": {}, "observation": "rollout complete"},
    ],
    "fire_count": 2,
    "time_to_resolve_seconds": 47,
}


class TestExtractSteps:

    def test_extracts_successful_actions(self, agent):
        steps = agent._extract_steps(RESOLVED_PAYLOAD["scratchpad"])
        assert len(steps) == 2
        assert "kubectl_patch" in steps[0]

    def test_skips_empty_actions(self, agent):
        steps = agent._extract_steps([{"action": "", "observation": "nothing"}])
        assert steps == []


class TestRun:

    @patch("backend.agents.learning_agent.ingest_text", return_value=True)
    @patch.object(LearningAgent, "_count_prior_resolutions", return_value=0)
    @patch.object(LearningAgent, "_maybe_promote_runbook", return_value=False)
    def test_ingests_resolved_outcome(self, _promote, _count, mock_ingest, agent):
        result = agent.run(RESOLVED_PAYLOAD)
        assert result["ingested"] is True
        assert result["doc_id"]
        mock_ingest.assert_called_once()

    def test_skips_non_resolved_outcome(self, agent):
        payload = {**RESOLVED_PAYLOAD, "outcome": "escalated"}
        result = agent.run(payload)
        assert result["ingested"] is False

    def test_requires_alert_name(self, agent):
        payload = {**RESOLVED_PAYLOAD, "alert_name": ""}
        with pytest.raises(ValueError):
            agent.run(payload)


class TestIngestFromExecution:

    @patch.object(LearningAgent, "execute")
    def test_delegates_resolved_snapshot(self, mock_execute, agent):
        mock_execute.return_value = {"ingested": True}
        snapshot = {
            "status": "resolved",
            "alert_name": "JavaPodOOMKilled",
            "namespace": "demo",
            "scratchpad": [],
            "final_summary": "fixed",
            "triage_summary": "oom",
        }
        agent.ingest_from_execution(snapshot, fire_count=3)
        mock_execute.assert_called_once()
        assert mock_execute.call_args[0][0]["fire_count"] == 3

    @patch.object(LearningAgent, "execute")
    def test_skips_unresolved(self, mock_execute, agent):
        result = agent.ingest_from_execution({"status": "escalated"})
        assert result["ingested"] is False
        mock_execute.assert_not_called()


class TestPromotion:

    @patch("backend.agents.learning_agent.ingest_directory")
    def test_promotion_writes_runbook_file(self, mock_ingest, agent, tmp_path):
        with patch("backend.agents.learning_agent.AUTO_RUNBOOK_DIR", tmp_path):
            promoted = agent._maybe_promote_runbook(
                alert_name="JavaPodOOMKilled",
                namespace="demo",
                resolution_steps=["kubectl patch deployment oom-demo"],
                final_summary="Memory limit increased",
            )
            assert promoted is True
            assert (tmp_path / "javapodoomkilled.md").exists()
            mock_ingest.assert_called_once()

    @patch("backend.agents.learning_agent.ingest_directory")
    def test_no_duplicate_promotion(self, mock_ingest, agent, tmp_path):
        path = tmp_path / "javapodoomkilled.md"
        path.write_text("existing")
        with patch("backend.agents.learning_agent.AUTO_RUNBOOK_DIR", tmp_path):
            promoted = agent._maybe_promote_runbook(
                alert_name="JavaPodOOMKilled",
                namespace="demo",
                resolution_steps=["step"],
                final_summary="summary",
            )
            assert promoted is False
            mock_ingest.assert_not_called()
