"""Unit tests for RunbookAgent — classify_risk() and step processing."""
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.documents import Document

from backend.agents.runbook_agent import RunbookAgent, classify_risk


def _doc(content: str, source: str = "pod_crashloop.md") -> tuple:
    return (Document(page_content=content, metadata={"source": source}), 0.1)


@pytest.fixture
def agent():
    return RunbookAgent()


@pytest.fixture
def payload():
    return {
        "alert_name": "PodCrashLoopBackOff",
        "description": "auth pod restarting every 30s",
    }


class TestClassifyRisk:

    # ── SAFE patterns ─────────────────────────────────────────────────────────

    def test_kubectl_get_is_safe(self):
        assert classify_risk("kubectl get pods -n iam") == "SAFE"

    def test_kubectl_describe_is_safe(self):
        assert classify_risk("kubectl describe pod auth-service-abc -n iam") == "SAFE"

    def test_kubectl_logs_is_safe(self):
        assert classify_risk("kubectl logs auth-service -n iam --previous") == "SAFE"

    def test_kubectl_top_is_safe(self):
        assert classify_risk("kubectl top pods -n iam") == "SAFE"

    def test_kubectl_rollout_status_is_safe(self):
        assert classify_risk("kubectl rollout status deployment/auth-service") == "SAFE"

    def test_curl_with_s_flag_is_safe(self):
        assert classify_risk("curl -s http://service:8080/health") == "SAFE"

    def test_curl_http_is_safe(self):
        assert classify_risk("curl http://localhost:9090/metrics") == "SAFE"

    def test_echo_is_safe(self):
        assert classify_risk("echo 'checking status'") == "SAFE"

    def test_cat_is_safe(self):
        assert classify_risk("cat /var/log/app.log") == "SAFE"

    def test_grep_is_safe(self):
        assert classify_risk("grep 'ERROR' /var/log/app.log") == "SAFE"

    def test_empty_command_is_safe(self):
        assert classify_risk("") == "SAFE"

    def test_whitespace_only_is_safe(self):
        assert classify_risk("   ") == "SAFE"

    # ── DANGEROUS patterns ────────────────────────────────────────────────────

    def test_kubectl_delete_is_dangerous(self):
        assert classify_risk("kubectl delete pod auth-abc -n iam") == "DANGEROUS"

    def test_kubectl_drain_is_dangerous(self):
        assert classify_risk("kubectl drain node01 --ignore-daemonsets") == "DANGEROUS"

    def test_kubectl_cordon_is_dangerous(self):
        assert classify_risk("kubectl cordon node01") == "DANGEROUS"

    def test_rm_rf_is_dangerous(self):
        assert classify_risk("rm -rf /data/chroma") == "DANGEROUS"

    def test_drop_table_is_dangerous(self):
        assert classify_risk("DROP TABLE sessions;") == "DANGEROUS"

    def test_drop_database_is_dangerous(self):
        assert classify_risk("DROP DATABASE prod_db;") == "DANGEROUS"

    def test_truncate_is_dangerous(self):
        assert classify_risk("TRUNCATE TABLE audit_logs;") == "DANGEROUS"

    def test_pg_terminate_is_dangerous(self):
        assert classify_risk("SELECT pg_terminate_backend(12345);") == "DANGEROUS"

    # ── REQUIRES_APPROVAL (default for unknown mutations) ─────────────────────

    def test_kubectl_apply_requires_approval(self):
        assert classify_risk("kubectl apply -f deployment.yaml") == "REQUIRES_APPROVAL"

    def test_kubectl_rollout_restart_requires_approval(self):
        assert classify_risk("kubectl rollout restart deployment/auth-service") == "REQUIRES_APPROVAL"

    def test_kubectl_set_resources_requires_approval(self):
        assert classify_risk("kubectl set resources deployment auth --limits=memory=1Gi") == "REQUIRES_APPROVAL"

    def test_kubectl_scale_requires_approval(self):
        assert classify_risk("kubectl scale deployment auth --replicas=3") == "REQUIRES_APPROVAL"

    def test_helm_upgrade_requires_approval(self):
        assert classify_risk("helm upgrade auth-service ./chart -n iam") == "REQUIRES_APPROVAL"

    # ── Case insensitivity ────────────────────────────────────────────────────

    def test_safe_patterns_case_insensitive(self):
        assert classify_risk("KUBECTL GET pods") == "SAFE"

    def test_dangerous_patterns_case_insensitive(self):
        assert classify_risk("Kubectl Delete pod xyz") == "DANGEROUS"


class TestRunbookAgentRun:

    def _setup_chain(self, mock_prompt, return_value: dict):
        # LCEL builds chain as (_PROMPT | llm) | parser — two levels of __or__
        mock_prompt.__or__.return_value.__or__.return_value.invoke.return_value = return_value

    def test_no_matching_runbook_returns_empty_steps(self, agent, payload):
        with patch.object(agent, "_retrieve", return_value=[]):
            result = agent.run(payload)

        assert result["steps"] == []
        assert result["pending_approval"] == []
        assert result["runbook_title"] == "No matching runbook found"
        assert result["runbook_source"] is None

    def test_steps_get_risk_level_assigned(self, agent, payload):
        llm_output = {
            "runbook_title": "Pod CrashLoop Runbook",
            "estimated_time": "10 minutes",
            "steps": [
                {"number": 1, "description": "Get pods", "command": "kubectl get pods -n iam", "expected_output": "Pod list"},
                {"number": 2, "description": "Restart", "command": "kubectl rollout restart deployment/auth", "expected_output": "Restarted"},
            ],
        }
        with patch.object(agent, "_retrieve", return_value=[_doc("runbook content")]), \
             patch.object(agent, "_route_llm") as mock_route:
            from backend.llm.router import LLMTier, Complexity
            mock_route.return_value = (MagicMock(), payload, LLMTier.LOCAL, Complexity.LOW)

            with patch("backend.agents.runbook_agent._PROMPT") as mock_prompt:
                self._setup_chain(mock_prompt, llm_output)
                result = agent.run(payload)

        assert result["steps"][0]["risk_level"] == "SAFE"
        assert result["steps"][1]["risk_level"] == "REQUIRES_APPROVAL"

    def test_pending_approval_excludes_safe_steps(self, agent, payload):
        llm_output = {
            "runbook_title": "Runbook",
            "estimated_time": "5 min",
            "steps": [
                {"number": 1, "description": "Check", "command": "kubectl get pods -n iam", "expected_output": ""},
                {"number": 2, "description": "Restart", "command": "kubectl rollout restart deployment/d", "expected_output": ""},
                {"number": 3, "description": "Delete", "command": "kubectl delete pod xyz", "expected_output": ""},
            ],
        }
        with patch.object(agent, "_retrieve", return_value=[_doc("content")]), \
             patch.object(agent, "_route_llm") as mock_route:
            from backend.llm.router import LLMTier, Complexity
            mock_route.return_value = (MagicMock(), payload, LLMTier.LOCAL, Complexity.LOW)

            with patch("backend.agents.runbook_agent._PROMPT") as mock_prompt:
                self._setup_chain(mock_prompt, llm_output)
                result = agent.run(payload)

        assert result["safe_steps_count"] == 1
        assert len(result["pending_approval"]) == 2

    def test_similarity_score_calculated_from_distance(self, agent, payload):
        with patch.object(agent, "_retrieve", return_value=[(_doc("content")[0], 0.2)]), \
             patch.object(agent, "_route_llm") as mock_route:
            from backend.llm.router import LLMTier, Complexity
            mock_route.return_value = (MagicMock(), payload, LLMTier.LOCAL, Complexity.LOW)

            with patch("backend.agents.runbook_agent._PROMPT") as mock_prompt:
                self._setup_chain(mock_prompt, {"runbook_title": "T", "estimated_time": "5m", "steps": []})
                result = agent.run(payload)

        assert result["similarity_score"] == pytest.approx(0.8, abs=0.01)

    def test_runbook_source_basename_only(self, agent, payload):
        doc = Document(page_content="content", metadata={"source": "/data/runbooks/pod_fix.md"})
        with patch.object(agent, "_retrieve", return_value=[(doc, 0.1)]), \
             patch.object(agent, "_route_llm") as mock_route:
            from backend.llm.router import LLMTier, Complexity
            mock_route.return_value = (MagicMock(), payload, LLMTier.LOCAL, Complexity.LOW)

            with patch("backend.agents.runbook_agent._PROMPT") as mock_prompt:
                self._setup_chain(mock_prompt, {"runbook_title": "T", "estimated_time": "5m", "steps": []})
                result = agent.run(payload)

        assert result["runbook_source"] == "pod_fix.md"
