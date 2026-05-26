"""Unit tests for ChatAgent — session persistence, RAG retrieval, prose output."""
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage

from backend.agents.chat_agent import ChatAgent
from backend.memory.session_store import InMemorySessionStore


def _doc(content: str, source: str = "runbook.md") -> tuple:
    return (Document(page_content=content, metadata={"source": source}), 0.15)


@pytest.fixture
def store():
    return InMemorySessionStore()


@pytest.fixture
def agent(store):
    return ChatAgent(store=store)


@pytest.fixture
def payload():
    return {"question": "How do I restart the auth pod?", "session_id": "sess-1"}


class TestFormatContext:

    def test_empty_returns_no_relevant_docs(self):
        result = ChatAgent._format_context([])
        assert "No relevant documents" in result

    def test_single_doc_includes_source_and_content(self):
        result = ChatAgent._format_context([_doc("kubectl rollout restart", "pod_restart.md")])
        assert "pod_restart.md" in result
        assert "kubectl rollout restart" in result

    def test_multiple_docs_separated_by_divider(self):
        docs = [_doc("content a", "a.md"), _doc("content b", "b.md")]
        result = ChatAgent._format_context(docs)
        assert "---" in result

    def test_long_content_truncated_at_600_chars(self):
        long_doc = _doc("X" * 1000, "big.md")
        result = ChatAgent._format_context([long_doc])
        assert "X" * 601 not in result  # content capped at 600

    def test_source_basename_only(self):
        doc = _doc("content", "/data/runbooks/oom_fix.md")
        result = ChatAgent._format_context([doc])
        assert "oom_fix.md" in result
        assert "/data/runbooks/" not in result


class TestChatAgentRun:

    def test_empty_question_returns_early(self, agent, store):
        result = agent.run({"question": "  ", "session_id": "sess-x"})
        assert result["answer"] == "Please provide a question."
        assert result["sources"] == []
        assert store.get_history("sess-x") == []

    def test_answer_stored_in_session(self, agent, store, payload):
        mock_response = MagicMock()
        mock_response.content = "Run kubectl rollout restart deployment/auth-service"

        with patch.object(agent, "_retrieve", return_value=[_doc("restart guide")]), \
             patch.object(agent, "_route_llm") as mock_route:
            from backend.llm.router import LLMTier, Complexity
            fake_chain = MagicMock()
            fake_chain.invoke.return_value = mock_response
            mock_route.return_value = (MagicMock(), payload, LLMTier.LOCAL, Complexity.LOW)

            with patch("backend.agents.chat_agent._PROMPT") as mock_prompt:
                mock_prompt.__or__ = MagicMock(return_value=fake_chain)
                agent.run(payload)

        history = store.get_history("sess-1")
        assert len(history) == 2  # HumanMessage + AIMessage
        assert isinstance(history[0], HumanMessage)
        assert isinstance(history[1], AIMessage)

    def test_history_injected_into_chain(self, agent, store, payload):
        store.add_exchange("sess-1", "prior question", "prior answer")
        mock_response = MagicMock()
        mock_response.content = "Here is the answer"
        captured_invoke_args = {}

        with patch.object(agent, "_retrieve", return_value=[]), \
             patch.object(agent, "_route_llm") as mock_route:
            from backend.llm.router import LLMTier, Complexity

            def capture_invoke(args):
                captured_invoke_args.update(args)
                return mock_response

            fake_chain = MagicMock()
            fake_chain.invoke.side_effect = capture_invoke
            mock_route.return_value = (MagicMock(), payload, LLMTier.LOCAL, Complexity.LOW)

            with patch("backend.agents.chat_agent._PROMPT") as mock_prompt:
                mock_prompt.__or__ = MagicMock(return_value=fake_chain)
                agent.run(payload)

        assert len(captured_invoke_args.get("history", [])) == 2

    def test_sources_deduplicated(self, agent, store, payload):
        docs = [
            _doc("content a", "runbook.md"),
            _doc("content b", "runbook.md"),  # same source, should be deduplicated
            _doc("content c", "arch.md"),
        ]
        mock_response = MagicMock()
        mock_response.content = "answer"

        with patch.object(agent, "_retrieve", side_effect=[docs[:2], docs[2:]]), \
             patch.object(agent, "_route_llm") as mock_route:
            from backend.llm.router import LLMTier, Complexity
            fake_chain = MagicMock()
            fake_chain.invoke.return_value = mock_response
            mock_route.return_value = (MagicMock(), payload, LLMTier.LOCAL, Complexity.LOW)

            with patch("backend.agents.chat_agent._PROMPT") as mock_prompt:
                mock_prompt.__or__ = MagicMock(return_value=fake_chain)
                result = agent.run(payload)

        assert result["sources"].count("runbook.md") == 1

    def test_result_includes_tier_and_complexity(self, agent, payload):
        mock_response = MagicMock()
        mock_response.content = "answer text"

        with patch.object(agent, "_retrieve", return_value=[]), \
             patch.object(agent, "_route_llm") as mock_route:
            from backend.llm.router import LLMTier, Complexity
            fake_chain = MagicMock()
            fake_chain.invoke.return_value = mock_response
            mock_route.return_value = (MagicMock(), payload, LLMTier.LOCAL, Complexity.LOW)

            with patch("backend.agents.chat_agent._PROMPT") as mock_prompt:
                mock_prompt.__or__ = MagicMock(return_value=fake_chain)
                result = agent.run(payload)

        assert result["llm_tier"] == "local"
        assert result["complexity"] == "low"
        assert result["session_id"] == "sess-1"

    def test_uses_default_store_when_none_provided(self):
        agent = ChatAgent()
        from backend.memory.persistence import session_store
        assert agent._store is session_store
