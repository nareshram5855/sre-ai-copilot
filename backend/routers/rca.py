from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import PlainTextResponse

from backend.agents.rca_agent import RCAAgent
from backend.integrations.slack import post_rca_complete
from backend.routers._models import RCAPayload, RCAResponse

router = APIRouter(prefix="/api/v1", tags=["rca"])

_agent = RCAAgent()


@router.post("/rca", response_model=RCAResponse)
def generate_rca(payload: RCAPayload, background_tasks: BackgroundTasks):
    """
    Generate a structured Root Cause Analysis from incident data.
    Returns JSON + pre-rendered markdown ready to paste into Confluence.
    """
    result = _agent.execute(payload.model_dump())
    if result.get("_meta", {}).get("error"):
        raise HTTPException(status_code=500, detail=result.get("error", "RCA generation failed"))
    result.pop("_meta", None)

    background_tasks.add_task(post_rca_complete, payload.title, result)

    return result


@router.post("/rca/markdown", response_class=PlainTextResponse)
def generate_rca_markdown(payload: RCAPayload):
    """Returns only the markdown — useful for piping directly to a file or Confluence API."""
    result = _agent.execute(payload.model_dump())
    if result.get("_meta", {}).get("error"):
        raise HTTPException(status_code=500, detail=result.get("error", "RCA generation failed"))
    return result.get("rca_markdown", "")
