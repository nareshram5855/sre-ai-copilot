from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.agents.triage_agent import TriageAgent
from backend.integrations.metrics import record_triage
from backend.integrations.slack import post_triage_alert
from backend.routers._models import AlertPayload, TriageResponse

router = APIRouter(prefix="/api/v1", tags=["triage"])

_agent = TriageAgent()


@router.post("/triage", response_model=TriageResponse)
def triage(alert: AlertPayload, background_tasks: BackgroundTasks):
    """
    Classify an incoming alert.

    Queries ChromaDB for similar past incidents, then asks the local LLM
    to assign severity (P1/P2/P3), confidence score, and suggested fix.
    Compatible with AlertManager webhook payload shape.
    """
    result = _agent.execute(alert.model_dump())
    if result.get("_meta", {}).get("error"):
        raise HTTPException(status_code=500, detail=result.get("error", "Triage failed"))
    result.pop("_meta", None)

    # Fire-and-forget: metrics + Slack — never block the HTTP response
    background_tasks.add_task(
        record_triage,
        severity=result.get("severity", "P2"),
        tier=result.get("llm_tier", "local"),
        escalated=result.get("escalate", False),
    )
    background_tasks.add_task(post_triage_alert, alert.name, result)

    return result


# ── Future agents — add routes here as phases progress ────────────────────────
#
# from backend.agents.runbook_agent import RunbookAgent
# _runbook_agent = RunbookAgent()
#
# @router.post("/runbook/execute", response_model=RunbookExecuteResponse)
# def execute_runbook(payload: RunbookExecutePayload):
#     result = _runbook_agent.execute(payload.model_dump())
#     result.pop("_meta", None)
#     return result
