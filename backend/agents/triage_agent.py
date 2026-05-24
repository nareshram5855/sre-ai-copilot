"""
Triage Agent — classifies alert severity using RAG + routed LLM.

Routing logic (handled by BaseAgent._route_llm):
  routine alert, similar incidents found  → Mistral 7B local   ($0)
  some uncertainty, few matches           → Gemini Flash        (~$0.11/mo)
  critical labels, risk keywords          → Claude Haiku        (~$2.40/mo)
  novel P1, zero RAG history              → Claude Sonnet       (pay-per-use)

Phase 2 enhancement — two-pass routing:
  Run Mistral first. If confidence < 0.6, re-run the same prompt
  with Claude Sonnet and return the stronger answer. Not implemented
  here to keep Phase 1 latency predictable.
"""
import json
from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from backend.agents.base import BaseAgent
from backend.config import settings

_SYSTEM = """You are a senior SRE on-call engineer at a financial services company.
Triage the incoming alert using the severity matrix and historical incidents below.

SEVERITY MATRIX:
- P1: Customer-facing outage, data loss risk, security breach, error rate >50%, SLA breach imminent
- P2: Degraded performance, error rate 10-50%, non-critical service down, SLO warning threshold crossed
- P3: Warning-level, non-urgent, cosmetic, low blast radius, can wait until business hours

SIMILAR PAST INCIDENTS (ranked by relevance):
{similar_incidents}

Respond with ONLY valid JSON — no markdown, no text outside the object:
{{
  "severity": "P1" | "P2" | "P3",
  "confidence": <float 0.0-1.0>,
  "reasoning": "<1-2 sentences explaining severity decision>",
  "suggested_fix": "<exact commands or step-by-step actions>",
  "similar_incidents": ["<brief summary of each relevant past incident>"],
  "escalate": <true if P1 or confidence < 0.6>,
  "estimated_impact": "<estimated users or services affected>"
}}"""

_HUMAN = """Alert Name: {alert_name}
Description: {alert_description}
Labels: {alert_labels}
Current Value: {alert_value}
Environment: {environment}
Firing Since: {firing_since}"""

_PROMPT = ChatPromptTemplate.from_messages([("system", _SYSTEM), ("human", _HUMAN)])


class TriageAgent(BaseAgent):

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        # Step 1: RAG retrieval — incidents + learned resolutions
        query = f"{payload.get('name', '')} {payload.get('description', '')}"
        incident_docs = self._retrieve(
            query=query,
            collection=settings.knowledge_collections["incidents"],
            k=3,
        )
        resolved_docs = self._retrieve(
            query=query,
            collection=settings.knowledge_collections["resolved_incidents"],
            k=2,
        )
        rag_docs = sorted(
            incident_docs + resolved_docs,
            key=lambda pair: pair[1],
        )[:4]
        rag_context, rag_summaries = self._format_rag(rag_docs)

        # Step 2: Route to the right LLM based on complexity signals
        llm, safe_payload, tier, complexity = self._route_llm(
            payload, rag_hit_count=len(rag_docs)
        )

        # Step 3: Run the chain
        chain = _PROMPT | llm | JsonOutputParser()
        result: dict = chain.invoke({
            "alert_name":        safe_payload.get("name", "Unknown Alert"),
            "alert_description": safe_payload.get("description", ""),
            "alert_labels":      json.dumps(safe_payload.get("labels", {}), indent=2),
            "alert_value":       str(safe_payload.get("value", "N/A")),
            "environment":       safe_payload.get("environment", "production"),
            "firing_since":      safe_payload.get("firing_since", "unknown"),
            "similar_incidents": rag_context,
        })

        # Step 4: Enrich with routing metadata (visible in API response + logs)
        if not result.get("similar_incidents") and rag_summaries:
            result["similar_incidents"] = rag_summaries
        result["llm_tier"] = tier.value
        result["complexity"] = complexity.value

        self.logger.info(
            "Triage '%s' → %s (confidence=%.2f, tier=%s, escalate=%s)",
            payload.get("name"), result.get("severity"),
            result.get("confidence", 0), tier.value, result.get("escalate"),
        )
        return result

    @staticmethod
    def _format_rag(docs_with_scores: list) -> tuple[str, list[str]]:
        if not docs_with_scores:
            return "No similar past incidents found in knowledge base.", []

        parts, summaries = [], []
        for doc, distance in docs_with_scores:
            similarity = max(0.0, 1.0 - distance)
            source = doc.metadata.get("source", "unknown").split("/")[-1]
            snippet = doc.page_content[:400].strip()
            parts.append(f"[similarity={similarity:.2f}] [{source}]\n{snippet}")
            summaries.append(f"{source} (sim={similarity:.2f}): {snippet[:100]}...")

        return "\n\n---\n\n".join(parts), summaries
