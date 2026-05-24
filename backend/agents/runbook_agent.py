"""
Runbook Executor — finds the matching runbook and classifies each step by risk.

Risk classification is intentionally conservative (default = REQUIRES_APPROVAL).
Safe patterns cover read-only kubectl/curl only. Any state mutation needs approval.
The UI gates approval — this agent never executes commands, only classifies them.

Why not auto-execute safe steps in the agent itself:
  Execution belongs in a separate service with audit logging, RBAC, and a kill switch.
  This agent's job is classification + structured output. Execution is handled by ExecutorAgent.
"""
import re
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from backend.agents.base import BaseAgent
from backend.config import settings

_SAFE_PATTERNS = [
    re.compile(r, re.IGNORECASE) for r in [
        r"^kubectl\s+get\b",
        r"^kubectl\s+describe\b",
        r"^kubectl\s+logs\b",
        r"^kubectl\s+top\b",
        r"^kubectl\s+rollout\s+status\b",
        r"^curl\s+-s",
        r"^curl\s+http",
        r"^echo\b",
        r"^cat\b",
        r"^grep\b",
    ]
]

_DANGEROUS_PATTERNS = [
    re.compile(r, re.IGNORECASE) for r in [
        r"kubectl\s+delete\b",
        r"kubectl\s+drain\b",
        r"kubectl\s+cordon\b",
        r"\brm\s+-rf\b",
        r"DROP\s+(TABLE|DATABASE)\b",
        r"TRUNCATE\b",
        r"pg_terminate_backend",
    ]
]

_SYSTEM = """You are an SRE runbook parser. Extract every actionable step from the runbook below.
For each step, extract the exact command (if any) and a brief description.
Return ONLY valid JSON:
{{
  "runbook_title": "<title>",
  "estimated_time": "<e.g. 10-15 minutes>",
  "steps": [
    {{
      "number": 1,
      "description": "<what this step does>",
      "command": "<exact command or empty string if no command>",
      "expected_output": "<what success looks like, or empty string>"
    }}
  ]
}}"""

_HUMAN = """Alert: {alert_name}
Description: {description}

Runbook content:
{runbook_content}"""

_PROMPT = ChatPromptTemplate.from_messages([("system", _SYSTEM), ("human", _HUMAN)])


def classify_risk(command: str) -> str:
    """
    Classify command risk level.
    Returns: SAFE | REQUIRES_APPROVAL | DANGEROUS
    Default is REQUIRES_APPROVAL — explicit allowlist, not denylist.
    """
    if not command.strip():
        return "SAFE"
    for pattern in _DANGEROUS_PATTERNS:
        if pattern.search(command):
            return "DANGEROUS"
    for pattern in _SAFE_PATTERNS:
        if pattern.match(command.strip()):
            return "SAFE"
    return "REQUIRES_APPROVAL"


class RunbookAgent(BaseAgent):

    def run(self, payload: dict) -> dict:
        alert_name = payload.get("alert_name", "")
        description = payload.get("description", "")

        docs = self._retrieve(
            f"{alert_name} {description}",
            settings.knowledge_collections["runbooks"],
            k=1,
        )

        if not docs:
            return {
                "runbook_source": None,
                "runbook_title": "No matching runbook found",
                "steps": [],
                "pending_approval": [],
                "estimated_time": "N/A",
                "llm_tier": "local",
            }

        top_doc, similarity = docs[0]
        runbook_content = top_doc.page_content
        runbook_source = top_doc.metadata.get("source", "unknown").split("/")[-1]

        llm, _, tier, _ = self._route_llm(payload, len(docs))
        chain = _PROMPT | llm | JsonOutputParser()

        result: dict = chain.invoke({
            "alert_name": alert_name,
            "description": description,
            "runbook_content": runbook_content[:3000],
        })

        steps = result.get("steps", [])
        for step in steps:
            step["risk_level"] = classify_risk(step.get("command", ""))

        pending = [s for s in steps if s["risk_level"] != "SAFE"]
        safe_count = sum(1 for s in steps if s["risk_level"] == "SAFE")

        self.logger.info(
            "Runbook '%s': %d steps, %d safe, %d pending approval",
            runbook_source, len(steps), safe_count, len(pending),
        )

        return {
            "runbook_source": runbook_source,
            "runbook_title": result.get("runbook_title", runbook_source),
            "estimated_time": result.get("estimated_time", "unknown"),
            "steps": steps,
            "safe_steps_count": safe_count,
            "pending_approval": pending,
            "similarity_score": round(max(0.0, 1.0 - similarity), 3),
            "llm_tier": tier.value,
        }
