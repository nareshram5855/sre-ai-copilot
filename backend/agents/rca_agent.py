"""
Auto RCA Generator — produces a structured Root Cause Analysis from incident data.

Always routed to ADVANCED or PREMIUM tier — RCA quality directly impacts
post-incident review, prevention planning, and regulatory audit trails.
A P1 RCA written by Claude Sonnet costs ~$0.05. Worth it.
"""
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from backend.agents.base import BaseAgent
from backend.config import settings
from backend.llm.router import LLMTier, get_llm

_SYSTEM = """You are a senior SRE writing a post-incident Root Cause Analysis (RCA).
Write a thorough, factual RCA based on the incident data and similar past incidents below.
Be specific — vague RCAs provide no learning value.

SIMILAR PAST INCIDENTS FOR CONTEXT:
{similar_incidents}

Return ONLY valid JSON:
{{
  "title": "<incident title>",
  "severity": "P1|P2|P3",
  "summary": "<2-3 sentence executive summary>",
  "root_cause": "<specific technical root cause — not symptoms>",
  "contributing_factors": ["<factor 1>", "<factor 2>"],
  "impact": {{
    "duration_minutes": <integer>,
    "users_affected": "<estimate>",
    "services_affected": ["<service 1>"]
  }},
  "timeline": [
    {{"time": "<HH:MM>", "event": "<what happened>", "actor": "system|engineer"}}
  ],
  "remediation": "<what was done to resolve the incident>",
  "prevention": ["<concrete action item 1>", "<concrete action item 2>"],
  "action_items": [
    {{"action": "<specific task>", "owner": "<team>", "priority": "P1|P2|P3", "due": "<timeframe>"}}
  ],
  "detection_gap": "<how long between incident start and alert fire — and why>"
}}"""

_HUMAN = """Incident Title: {title}
Severity: {severity}
Environment: {environment}
Affected Services: {affected_services}
Duration: {duration_minutes} minutes
Timeline Events:
{timeline}
Resolution Summary: {resolution}"""

_PROMPT = ChatPromptTemplate.from_messages([("system", _SYSTEM), ("human", _HUMAN)])

_RCA_MD_TEMPLATE = """\
# RCA: {title}

**Severity:** {severity} | **Duration:** {duration_minutes} min | **Status:** Resolved

## Summary
{summary}

## Root Cause
{root_cause}

## Contributing Factors
{contributing_factors}

## Impact
- **Users affected:** {users_affected}
- **Services affected:** {services_affected}
- **Detection gap:** {detection_gap}

## Timeline
{timeline_table}

## Remediation
{remediation}

## Prevention
{prevention}

## Action Items
{action_items_table}
"""


class RCAAgent(BaseAgent):

    def run(self, payload: dict) -> dict:
        title = payload.get("title", "Untitled Incident")

        docs = self._retrieve(title, settings.knowledge_collections["incidents"], k=3)
        context = self._format_similar(docs)

        # RCA always deserves at minimum ADVANCED tier — override complexity scoring
        from backend.config import get_settings
        cfg = get_settings()
        tier = LLMTier.ADVANCED if cfg.allow_external_llm and cfg.anthropic_api_key else LLMTier.LOCAL
        llm = get_llm(tier)

        from backend.llm.sanitizer import sanitize
        safe = sanitize(payload)

        chain = _PROMPT | llm | JsonOutputParser()
        result: dict = chain.invoke({
            "title":             safe.get("title", title),
            "severity":          safe.get("severity", "P2"),
            "environment":       safe.get("environment", "production"),
            "affected_services": ", ".join(safe.get("affected_services", [])),
            "duration_minutes":  safe.get("duration_minutes", 0),
            "timeline":          self._format_timeline_text(safe.get("timeline", [])),
            "resolution":        safe.get("resolution", ""),
            "similar_incidents": context,
        })

        result["rca_markdown"] = self._render_markdown(result)
        result["llm_tier"] = tier.value

        self.logger.info("RCA generated for '%s' (tier=%s)", title, tier.value)
        return result

    @staticmethod
    def _format_similar(docs_with_scores: list) -> str:
        if not docs_with_scores:
            return "No similar past incidents found."
        parts = []
        for doc, dist in docs_with_scores:
            sim = max(0.0, 1.0 - dist)
            src = doc.metadata.get("source", "unknown").split("/")[-1]
            parts.append(f"[{src}] (sim={sim:.2f})\n{doc.page_content[:400].strip()}")
        return "\n\n---\n\n".join(parts)

    @staticmethod
    def _format_timeline_text(events: list[dict]) -> str:
        return "\n".join(f"- {e.get('time', '??:??')}: {e.get('event', '')}" for e in events)

    @staticmethod
    def _render_markdown(r: dict) -> str:
        timeline_rows = "\n".join(
            f"| {e.get('time','?')} | {e.get('actor','?')} | {e.get('event','?')} |"
            for e in r.get("timeline", [])
        )
        timeline_table = f"| Time | Actor | Event |\n|---|---|---|\n{timeline_rows}" if timeline_rows else "No timeline provided."

        action_rows = "\n".join(
            f"| {a.get('action','?')} | {a.get('owner','?')} | {a.get('priority','?')} | {a.get('due','?')} |"
            for a in r.get("action_items", [])
        )
        action_table = f"| Action | Owner | Priority | Due |\n|---|---|---|---|\n{action_rows}" if action_rows else "No action items."

        impact = r.get("impact", {})
        return _RCA_MD_TEMPLATE.format(
            title=r.get("title", ""),
            severity=r.get("severity", ""),
            duration_minutes=impact.get("duration_minutes", 0),
            summary=r.get("summary", ""),
            root_cause=r.get("root_cause", ""),
            contributing_factors="\n".join(f"- {f}" for f in r.get("contributing_factors", [])),
            users_affected=impact.get("users_affected", "unknown"),
            services_affected=", ".join(impact.get("services_affected", [])),
            detection_gap=r.get("detection_gap", "unknown"),
            timeline_table=timeline_table,
            remediation=r.get("remediation", ""),
            prevention="\n".join(f"- {p}" for p in r.get("prevention", [])),
            action_items_table=action_table,
        )
