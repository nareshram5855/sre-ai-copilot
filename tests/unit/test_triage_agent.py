"""Unit tests for TriageAgent — mocks LLM and RAG, tests OUR logic."""
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.documents import Document

from backend.agents.triage_agent import TriageAgent


def _doc(content: str, source: str = "incident.md") -> tuple:
    doc = Document(page_content=content, metadata={"source": source})
    return (doc, 0.2)  # distance 0.2 → similarity 0.8


_LLM_RESULT = {
    "severity": "P2",
    "confidence": 0.82,
    "reasoning": "Elevated error rate but no full outage.",
    "suggested_fix": "kubectl rollout restart deployment/auth-service -n iam",
    "similar_incidents": [],
    "escalate": False,
    "estimated_impact": "~300 users",
}


@pytest.fixture
def agent():
    return TriageAgent()


@pytest.fixture
def alert():
    return {
        "name": "HighErrorRate",
        "description": "auth-service error rate at 25%",
        "labels": {"severity": "warning"},
        "environment": "production",
        "value": 25.3,
    }


class TestFormatRag:

    def test_empty_list_returns_no_incidents_message(self):
        text, summaries = TriageAgent._format_rag([])
        assert "No similar past incidents" in text
        assert summaries == []

    def test_single_doc_formatted_correctly(self):
        text, summaries = TriageAgent._format_rag([_doc("OOM kill in auth-service Jan 2024")])
        assert "similarity=" in text
        assert "incident.md" in text
        assert len(summaries) == 1

    def test_similarity_calculated_from_distance(self):
        # distance=0.0 → similarity=1.0
        doc = Document(page_content="content", metadata={"source": "x.md"})
        text, _ = TriageAgent._format_rag([(doc, 0.0)])
        assert "similarity=1.00" in text

    def test_distance_gt_1_clamped_to_zero_similarity(self):
        doc = Document(page_content="content", metadata={"source": "x.md"})
        text, _ = TriageAgent._format_rag([(doc, 1.5)])
        assert "similarity=0.00" in text

    def test_source_basename_used(self):
        doc = Document(page_content="x", metadata={"source": "/data/incidents/oom_kill.md"})
        text, _ = TriageAgent._format_rag([(doc, 0.1)])
        assert "oom_kill.md" in text
        assert "/data/incidents/" not in text

    def test_long_content_truncated(self):
        long_content = "A" * 1000
        doc = Document(page_content=long_content, metadata={"source": "x.md"})
        text, summaries = TriageAgent._format_rag([(doc, 0.1)])
        # snippet is max 400 chars in text, 100 in summary
        assert len(summaries[0]) < 300  # well under full content

    def test_multiple_docs_separated_by_divider(self):
        docs = [_doc("incident one", "a.md"), _doc("incident two", "b.md")]
        text, summaries = TriageAgent._format_rag(docs)
        assert "---" in text
        assert len(summaries) == 2


class TestTriageAgentRun:

    def _setup_chain(self, mock_prompt, return_value: dict):
        # LCEL builds chain as (_PROMPT | llm) | parser — two levels of __or__
        mock_prompt.__or__.return_value.__or__.return_value.invoke.return_value = return_value

    def test_llm_result_enriched_with_tier_and_complexity(self, agent, alert):
        with patch.object(agent, "_retrieve", return_value=[_doc("OOM incident")]), \
             patch.object(agent, "_route_llm") as mock_route:
            from backend.llm.router import LLMTier, Complexity
            mock_route.return_value = (MagicMock(), alert, LLMTier.LOCAL, Complexity.LOW)

            with patch("backend.agents.triage_agent._PROMPT") as mock_prompt:
                self._setup_chain(mock_prompt, dict(_LLM_RESULT))
                result = agent.run(alert)

        assert result["llm_tier"] == "local"
        assert result["complexity"] == "low"

    def test_rag_summaries_backfill_when_llm_returns_none(self, agent, alert):
        with patch.object(agent, "_retrieve", return_value=[_doc("Known incident", "ref.md")]), \
             patch.object(agent, "_route_llm") as mock_route:
            from backend.llm.router import LLMTier, Complexity
            mock_route.return_value = (MagicMock(), alert, LLMTier.LOCAL, Complexity.LOW)

            with patch("backend.agents.triage_agent._PROMPT") as mock_prompt:
                self._setup_chain(mock_prompt, {**_LLM_RESULT, "similar_incidents": []})
                result = agent.run(alert)

        assert len(result["similar_incidents"]) > 0

    def test_no_rag_docs_still_runs(self, agent, alert):
        with patch.object(agent, "_retrieve", return_value=[]), \
             patch.object(agent, "_route_llm") as mock_route:
            from backend.llm.router import LLMTier, Complexity
            mock_route.return_value = (MagicMock(), alert, LLMTier.LOCAL, Complexity.CRITICAL)

            with patch("backend.agents.triage_agent._PROMPT") as mock_prompt:
                self._setup_chain(mock_prompt, dict(_LLM_RESULT))
                result = agent.run(alert)

        assert result["severity"] == "P2"

    def test_execute_wraps_run_with_meta(self, agent, alert):
        with patch.object(agent, "run", return_value=dict(_LLM_RESULT)) as mock_run:
            result = agent.execute(alert)

        mock_run.assert_called_once_with(alert)
        assert "_meta" in result
        assert result["_meta"]["agent"] == "TriageAgent"
        assert result["_meta"]["duration_seconds"] >= 0

    def test_execute_returns_fallback_on_exception(self, agent, alert):
        with patch.object(agent, "run", side_effect=RuntimeError("Ollama down")):
            result = agent.execute(alert)

        assert result["_meta"]["error"] is True
        assert result["escalate"] is True
        assert "Ollama down" in result["error"]
