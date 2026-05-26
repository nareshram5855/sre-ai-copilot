"""
Incidents router — execution control plane for ExecutorAgent + Supervisor.

Endpoints:
  POST /api/v1/ask                              → Supervisor: classify + route to specialist
  POST /api/v1/incidents/{id}/execute           → Start ExecutorAgent ReAct loop
  POST /api/v1/incidents/{id}/approve/{exec_id} → Resume after human approval
  GET  /api/v1/incidents/{id}/execution/{exec_id} → Poll execution state + scratchpad
  POST /api/v1/incidents/{id}/resolve              → Mark outcome + trigger learning
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.agents.executor_agent import (
    executor_agent,
    list_read_actions,
    list_write_actions,
    stream_execution_events,
)
from backend.agents.learning_agent import learning_agent
from backend.agents.supervisor_agent import supervisor_agent
from backend.integrations import pagerduty, servicenow
from backend.routers._security import require_api_key
from backend.routers.alertmanager import get_fire_count, get_recent_triage

logger = logging.getLogger(__name__)
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


@router.post("/api/v1/incidents/{incident_id}/execute", dependencies=[Depends(require_api_key)])
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


@router.post("/api/v1/incidents/{incident_id}/approve/{execution_id}", dependencies=[Depends(require_api_key)])
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
    servicenow_number: str = Field(default="", description="Existing INC# to attach RCA to")


@router.post("/api/v1/incidents/{incident_id}/resolve", dependencies=[Depends(require_api_key)])
def resolve_incident(incident_id: str, body: ResolveRequest) -> dict:
    """
    Human feedback endpoint — mark incident outcome, trigger auto-learning,
    page-resolve in PagerDuty, and attach the RCA back to ServiceNow.
    """
    alert_name = body.alert_name
    namespace = body.namespace
    snapshot: dict | None = None

    if body.execution_id:
        snapshot = executor_agent.get(body.execution_id)
        if snapshot:
            snapshot["status"] = body.outcome
            if body.final_summary:
                snapshot["final_summary"] = body.final_summary
            alert_name = alert_name or snapshot.get("alert_name", "")
            namespace = namespace or snapshot.get("namespace", "")
            learning = learning_agent.ingest_from_execution(
                snapshot,
                fire_count=get_fire_count(alert_name, namespace),
            )
        else:
            learning = {"ingested": False, "reason": f"execution {body.execution_id} not found"}
    else:
        payload = {
            "alert_name": alert_name,
            "namespace": namespace,
            "outcome": body.outcome,
            "scratchpad": body.scratchpad,
            "final_summary": body.final_summary,
            "triage_summary": body.triage_summary,
            "fire_count": get_fire_count(alert_name, namespace),
        }
        learning = learning_agent.execute(payload)

    prior_resolutions = learning_agent.count_prior_resolutions(alert_name, namespace)

    # ── Side-effects: page resolve + attach RCA ────────────────────────────
    side_effects: dict = {}
    if alert_name and body.outcome == "resolved":
        if pagerduty.is_configured():
            side_effects["pagerduty_resolved"] = pagerduty.resolve(
                dedup_key=pagerduty.dedup_key_for(alert_name, namespace),
                summary=body.final_summary or f"{alert_name} resolved by SRE AI Copilot",
            )
        if body.servicenow_number and servicenow.is_configured():
            rca = _build_resolution_markdown(alert_name, namespace, body, snapshot, learning)
            side_effects["servicenow_attached"] = servicenow.attach_rca(
                incident_number=body.servicenow_number,
                rca_markdown=rca,
                final_summary=body.final_summary,
            )

    return {
        "incident_id": incident_id,
        "outcome": body.outcome,
        "learning": learning,
        "prior_resolutions": prior_resolutions,
        "side_effects": side_effects,
    }


# ── Escalation: human declined a write action ───────────────────────────────

class EscalateRequest(BaseModel):
    alert_name: str
    namespace: str = ""
    summary: str = "Manual approval declined — paging on-call"
    severity: str = "P1"
    execution_id: str = ""
    triage_summary: str = ""


@router.post("/api/v1/incidents/{incident_id}/escalate", dependencies=[Depends(require_api_key)])
def escalate_incident(incident_id: str, body: EscalateRequest) -> dict:
    """
    Page on-call via PagerDuty + open a fresh ServiceNow incident (if not done already).
    Called from ExecutionDrawer when the engineer rejects an auto-remediation.
    """
    pd_triggered = False
    snow_number: str | None = None
    if pagerduty.is_configured():
        pd_triggered = pagerduty.trigger(
            dedup_key=pagerduty.dedup_key_for(body.alert_name, body.namespace),
            summary=body.summary,
            severity=body.severity,
            custom_details={
                "incident_id": incident_id,
                "execution_id": body.execution_id,
                "namespace": body.namespace,
                "triage_summary": body.triage_summary[:500],
            },
        )
    if servicenow.is_configured():
        snow_number = servicenow.create_incident(
            alert_name=body.alert_name,
            namespace=body.namespace,
            severity=body.severity,
            summary=body.summary,
            extra={"incident_id": incident_id, "execution_id": body.execution_id},
        )
    return {
        "incident_id": incident_id,
        "pagerduty_triggered": pd_triggered,
        "servicenow_number": snow_number,
    }


# ── System info: write-action registry + integrations status ────────────────

@router.get("/api/v1/incidents/system/actions")
def list_actions() -> dict:
    """Single source of truth — used by frontend to flag write actions."""
    return {
        "write_actions": list_write_actions(),
        "read_actions": list_read_actions(),
    }


@router.get("/api/v1/incidents/system/integrations")
def integrations_status() -> dict:
    """Tell the frontend which side-effect integrations are configured."""
    return {
        "pagerduty": pagerduty.is_configured(),
        "servicenow": servicenow.is_configured(),
    }


# ── helpers ─────────────────────────────────────────────────────────────────

def _build_resolution_markdown(
    alert_name: str,
    namespace: str,
    body: ResolveRequest,
    snapshot: dict | None,
    learning: dict,
) -> str:
    lines = [
        f"# Resolution — {alert_name}",
        "",
        f"- **Namespace:** `{namespace}`",
        f"- **Outcome:** {body.outcome}",
        f"- **Execution ID:** `{body.execution_id or '(manual)'}`",
        f"- **Learning ingested:** {learning.get('ingested')}",
        "",
    ]
    if body.final_summary:
        lines += ["## Summary", body.final_summary, ""]
    elif snapshot and snapshot.get("final_summary"):
        lines += ["## Summary", snapshot["final_summary"], ""]
    scratchpad = body.scratchpad or (snapshot.get("scratchpad", []) if snapshot else [])
    if scratchpad:
        lines += ["## Steps"]
        for i, step in enumerate(scratchpad, 1):
            action = step.get("action", "?")
            args = step.get("args") or {}
            args_str = " ".join(f"{k}={v}" for k, v in args.items() if v)
            lines.append(f"{i}. `{action} {args_str}`")
        lines.append("")
    lines.append("_Auto-generated by SRE AI Copilot._")
    return "\n".join(lines)
