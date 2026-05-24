"""
BaseAgent — shared foundation for every SRE AI agent.

Every agent inherits:
  - _route_llm()     select the right LLM tier based on complexity signals
  - _retrieve()      RAG retrieval with graceful fallback
  - execute()        wraps run() with timing, logging, error handling
  - _fallback_response()  safe default when the LLM is unavailable

Adding a new agent:
  class MyAgent(BaseAgent):
      def run(self, payload): ...   ← only domain logic here
"""
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from langchain_core.language_models import BaseChatModel

from backend.llm.router import (
    Complexity,
    LLMTier,
    audit_log,
    get_llm,
    resolve_tier,
    score_complexity,
)
from backend.llm.sanitizer import sanitize
from backend.rag.retriever import retrieve_with_score


class BaseAgent(ABC):

    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)

    # ── LLM routing ───────────────────────────────────────────────────────────

    def _route_llm(
        self,
        payload: dict[str, Any],
        rag_hit_count: int,
        *,
        json_mode: bool = True,
    ) -> tuple[BaseChatModel, dict[str, Any], LLMTier, Complexity]:
        """
        Score complexity → pick LLM tier → sanitize if external → audit log.

        Returns:
            llm:        the selected LangChain chat model
            safe_payload: sanitized payload (same as input for LOCAL tier)
            tier:       which tier was selected
            complexity: the scored complexity level
        """
        complexity = score_complexity(payload, rag_hit_count)
        tier = resolve_tier(complexity)
        llm = get_llm(tier, json_mode=json_mode)

        safe_payload = sanitize(payload) if tier != LLMTier.LOCAL else payload
        audit_log(tier, complexity, safe_payload)

        self.logger.info(
            "LLM routing: complexity=%s tier=%s rag_hits=%d",
            complexity.value, tier.value, rag_hit_count,
        )
        return llm, safe_payload, tier, complexity

    # ── RAG helper ────────────────────────────────────────────────────────────

    def _retrieve(
        self, query: str, collection: str, k: int = 4
    ) -> list[tuple[Any, float]]:
        """Scored retrieval. Returns [] gracefully if ChromaDB is unreachable."""
        return retrieve_with_score(query=query, collection_name=collection, k=k)

    # ── Contract ──────────────────────────────────────────────────────────────

    @abstractmethod
    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Implement agent logic. Raise on unrecoverable errors."""
        ...

    # ── Public entry point ────────────────────────────────────────────────────

    def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Routers call this — never run() directly."""
        name = self.__class__.__name__
        start = time.monotonic()
        self.logger.info("%s started", name)

        try:
            result = self.run(payload)
            elapsed = round(time.monotonic() - start, 3)
            self.logger.info("%s completed in %.3fs", name, elapsed)
            result["_meta"] = {"agent": name, "duration_seconds": elapsed}
            return result
        except Exception as exc:
            elapsed = round(time.monotonic() - start, 3)
            self.logger.error("%s failed after %.3fs: %s", name, elapsed, exc, exc_info=True)
            return {
                **self._fallback_response(str(exc)),
                "_meta": {"agent": name, "duration_seconds": elapsed, "error": True},
            }

    def _fallback_response(self, error: str) -> dict[str, Any]:
        """Conservative safe default — subclasses can override for domain-specific fallbacks."""
        return {
            "error": error,
            "severity": "P2",
            "confidence": 0.0,
            "reasoning": f"Agent unavailable — safe P2 default applied. Error: {error}",
            "suggested_fix": "Check Ollama: ollama ps && ollama serve",
            "similar_incidents": [],
            "escalate": True,
            "estimated_impact": "Unknown",
        }
