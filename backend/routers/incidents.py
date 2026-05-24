"""
Incidents router — execution control plane for ExecutorAgent + Supervisor.

Endpoints:
  POST /api/v1/ask                              → Supervisor: classify + route to specialist
  POST /api/v1/incidents/{id}/execute           → Start ExecutorAgent ReAct loop
  POST /api/v1/incidents/{id}/approve/{exec_id} → Resume after human approval
  GET  /api/v1/incidents/{id}/execution/{exec_id} → Poll execution state + scratchpad
  POST /api/v1/incidents/{id}/resolve              → Mark outcome + trigger learning
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.agents.executor_agent import executor_agent, stream_execution_events
from backend.agents.learning_agent import learning_agent
from backend.agents.supervisor_agent import supervisor_agent
from backend.routers.alertmanager import get_fire_count

router = APIRouter(tags=["incidents"])


# ── Supervisor endpoint ───────────────────────────────────────────────────────

class AskRequest(BaseModel):
    input: str          # raw natural language or alert description
    payload: dict = {}  # optional structured fields (alert labels, question, etc.)


@router.post("/api/v1/ask")
def ask(body: AskRequest) -> dict:
    """
    Single entry point for all SRE AI capabilities.

    The Supervisor LangGraph:
      1. Classifies intent (triage / chat / runbook / rca / execute)
      2. Routes to the correct specialist agent node
      3. Merges and returns a normalized result

    Example inputs:
      {"input": "OOMKilled in demo namespace", "payload": {"name": "JavaPodOOMKilled", ...}}
      {"input": "How do I fix a CrashLoopBackOff?"}
      {"input": "Run the db connection pool runbook", "payload": {"issue_type": "db_connection_pool"}}
    """
    return supervisor_agent.run(raw_input=body.input, payload=body.payload)


# ── ExecutorAgent endpoints ───────────────────────────────────────────────────

class ExecuteRequest(BaseModel):
    alert_name:     str
    namespace:      str
    triage_summary: str


@router.post("/api/v1/incidents/{incident_id}/execute")
def start_execution(incident_id: str, body: ExecuteRequest) -> dict:
    """
    Start an autonomous remediation run.

    The LangGraph ExecutorAgent:
      1. Dispatches get_pods + get_logs + top_pods IN PARALLEL (3x faster gather)
      2. Reasons over the merged cluster state
      3. Runs read tools automatically
      4. PAUSES before write tools (interrupt_before=execute_write)
      5. Returns {status: "waiting_approval", pending_action: {...}} to the frontend

    The frontend shows an "Approve?" modal. When the engineer approves,
    call POST /approve/{execution_id} to resume.
    """
    result = executor_agent.start(
        incident_id=incident_id,
        alert_name=body.alert_name,
        namespace=body.namespace,
        triage_summary=body.triage_summary,
    )
    if result is None:
        raise HTTPException(status_code=500, detail="Execution failed to start")
    return result


@router.post("/api/v1/incidents/{incident_id}/approve/{execution_id}")
def approve_action(incident_id: str, execution_id: str) -> dict:
    """
    Resume a paused execution after human approval.

    Internally calls graph.invoke(None, config={"thread_id": execution_id}).
    LangGraph rehydrates state from MemorySaver and continues from the
    interrupted execute_write node.

    Safe to call multiple times — each call resumes from the next interrupt.
    """
    try:
        result = executor_agent.approve(execution_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if result is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return result


@router.get("/api/v1/incidents/{incident_id}/execution/{execution_id}/stream")
def stream_execution(incident_id: str, execution_id: str) -> StreamingResponse:
    """
    SSE stream of execution events — frontend connects with EventSource.

    Event types pushed in real-time:
      start     → execution started {alert_name, namespace}
      gather    → parallel gather node {label: pods|logs|metrics, status: running|done, output?}
      thinking  → LLM reasoning started {step, message}
      decision  → LLM chose an action {thought, action, args, done, escalate}
      step      → tool executed {thought, action, args, observation, write, step_num}
      approved  → write action approved by human {action, args}
      done      → stream ended (graph resolved or escalated)
      heartbeat → keepalive every 30s
      error     → error condition
    """
    return StreamingResponse(
        stream_execution_events(execution_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
        },
    )


@router.get("/api/v1/incidents/{incident_id}/execution/{execution_id}")
def get_execution(incident_id: str, execution_id: str) -> dict:
    """
    Poll execution state — frontend calls this every 2s to render the live trace.

    Returns:
      - status: running | waiting_approval | resolved | escalated | failed
      - scratchpad: [{thought, action, args, observation, write}, ...]
      - pending_action: the write action awaiting approval (if status=waiting_approval)
      - pods_info / logs_info / metrics_info: parallel gather results
    """
    result = executor_agent.get(execution_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return result


class ResolveRequest(BaseModel):
    outcome: str = Field(default="resolved", description="resolved | escalated | failed")
    alert_name: str = ""
    namespace: str = ""
    final_summary: str = ""
    triage_summary: str = ""
    scratchpad: list[dict] = Field(default_factory=list)
    execution_id: str = ""


@router.post("/api/v1/incidents/{incident_id}/resolve")
def resolve_incident(incident_id: str, body: ResolveRequest) -> dict:
    """
    Human feedback endpoint — mark incident outcome and trigger auto-learning.

    Called when an engineer confirms a manual fix worked, or to backfill learning
    from a completed ExecutorAgent run.
    """
    if body.execution_id:
        snapshot = executor_agent.get(body.execution_id)
        if snapshot:
            snapshot["status"] = body.outcome
            if body.final_summary:
                snapshot["final_summary"] = body.final_summary
            result = learning_agent.ingest_from_execution(
                snapshot,
                fire_count=get_fire_count(snapshot.get("alert_name", ""), snapshot.get("namespace", "")),
            )
            return {"incident_id": incident_id, "learning": result}

    payload = {
        "alert_name": body.alert_name,
        "namespace": body.namespace,
        "outcome": body.outcome,
        "scratchpad": body.scratchpad,
        "final_summary": body.final_summary,
        "triage_summary": body.triage_summary,
        "fire_count": get_fire_count(body.alert_name, body.namespace),
    }
    result = learning_agent.execute(payload)
    return {"incident_id": incident_id, "learning": result}
