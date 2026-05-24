from fastapi import APIRouter, HTTPException

from backend.agents.runbook_agent import RunbookAgent
from backend.routers._models import RunbookPayload, RunbookResponse

router = APIRouter(prefix="/api/v1", tags=["runbook"])

_agent = RunbookAgent()


@router.post("/runbook/execute", response_model=RunbookResponse)
def execute_runbook(payload: RunbookPayload):
    """
    Find the matching runbook for an alert and classify each step by risk.

    Returns:
      - steps: all parsed steps with risk_level (SAFE | REQUIRES_APPROVAL | DANGEROUS)
      - pending_approval: steps that require human sign-off before execution
      - safe_steps_count: steps that are pre-approved read-only operations

    The UI gates execution — this endpoint never runs commands.
    """
    result = _agent.execute(payload.model_dump())
    if result.get("_meta", {}).get("error"):
        raise HTTPException(status_code=500, detail=result.get("error", "Runbook execution failed"))
    result.pop("_meta", None)
    return result
