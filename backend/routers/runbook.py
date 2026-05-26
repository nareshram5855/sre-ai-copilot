import asyncio
import json
import logging
import shlex
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.agents.runbook_agent import RunbookAgent, classify_risk
from backend.memory.audit_store import log_execution_audit
from backend.routers._models import RunbookPayload, RunbookResponse
from backend.routers._security import require_api_key
from backend.routers._shell_security import check_command

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["runbook"])

_agent = RunbookAgent()
_AUTO_DIR = Path(__file__).parent.parent / "knowledge" / "runbooks" / "auto"
_RUNBOOKS_DIR = Path(__file__).parent.parent / "knowledge" / "runbooks"


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


# ── Single-step execution (goes through the same shell security + audit) ────

class StepExecuteRequest(BaseModel):
    runbook_source: str = Field(default="", description="filename of the source runbook")
    step_number: int = 0
    command: str
    description: str = ""
    risk_level: str = Field(default="REQUIRES_APPROVAL")
    approved: bool = Field(default=False, description="must be true for non-SAFE steps")
    session_id: str = ""


@router.post("/runbook/execute-step", dependencies=[Depends(require_api_key)])
async def execute_step(body: StepExecuteRequest) -> StreamingResponse:
    """
    Stream stdout/stderr of a single runbook step.

    Security model:
      - Risk classification is re-verified server-side (clients can't claim SAFE).
      - DANGEROUS commands are always blocked.
      - REQUIRES_APPROVAL commands need ``approved=True`` and a valid API key.
      - All executions are audit-logged with execution_id = runbook_source:step#.
    """
    command = body.command.strip()
    if not command:
        raise HTTPException(status_code=400, detail="Command is required")

    server_risk = classify_risk(command)
    if server_risk == "DANGEROUS":
        raise HTTPException(status_code=403, detail="Command is DANGEROUS — refuse to run")
    if server_risk != "SAFE" and not body.approved:
        raise HTTPException(status_code=403, detail=f"Step is {server_risk} — approval required")

    # Shell security gate (denies things like delete/exec/cp/pf even on kubectl)
    allowed, reason = check_command(command, full_mode=False)
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Shell security: {reason}")

    execution_id = body.session_id or f"runbook-{uuid.uuid4().hex[:8]}"
    incident_id = body.runbook_source or "runbook"

    async def _stream():
        log_execution_audit(
            execution_id=execution_id,
            incident_id=incident_id,
            action_type="runbook_step",
            tool_name=f"step#{body.step_number}",
            command_details={"command": command, "description": body.description, "risk": server_risk},
            status="started",
            approval_required=server_risk != "SAFE",
            approved_by="engineer" if body.approved else "",
        )
        yield f"data: {json.dumps({'type': 'allowed', 'command': command, 'risk': server_risk})}\n\n"
        try:
            args = shlex.split(command)
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            assert proc.stdout and proc.stderr
            async for raw in proc.stdout:
                line = raw.decode(errors="replace").rstrip()
                if line:
                    yield f"data: {json.dumps({'type': 'stdout', 'line': line})}\n\n"
            async for raw in proc.stderr:
                line = raw.decode(errors="replace").rstrip()
                if line:
                    yield f"data: {json.dumps({'type': 'stderr', 'line': line})}\n\n"
            try:
                await asyncio.wait_for(proc.wait(), timeout=60)
            except asyncio.TimeoutError:
                proc.kill()
                yield f"data: {json.dumps({'type': 'error', 'message': 'Step timed out (60s)'})}\n\n"
                log_execution_audit(
                    execution_id=execution_id,
                    incident_id=incident_id,
                    action_type="runbook_step",
                    tool_name=f"step#{body.step_number}",
                    status="error",
                    error="timeout",
                )
                return
            yield f"data: {json.dumps({'type': 'done', 'exit_code': proc.returncode})}\n\n"
            log_execution_audit(
                execution_id=execution_id,
                incident_id=incident_id,
                action_type="runbook_step",
                tool_name=f"step#{body.step_number}",
                command_details={"command": command, "exit_code": proc.returncode},
                status="success" if proc.returncode == 0 else "error",
                error="" if proc.returncode == 0 else f"exit_code={proc.returncode}",
            )
        except FileNotFoundError as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': f'tool not found: {exc.filename}'})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
            log_execution_audit(
                execution_id=execution_id,
                incident_id=incident_id,
                action_type="runbook_step",
                tool_name=f"step#{body.step_number}",
                status="error",
                error=str(exc),
            )

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ── Runbook library (auto-promoted + bundled markdown) ───────────────────────

@router.get("/runbook/library")
def runbook_library() -> dict:
    """List bundled + auto-promoted runbooks for the Playbooks panel."""
    bundled: list[dict] = []
    auto: list[dict] = []

    if _RUNBOOKS_DIR.exists():
        for path in sorted(_RUNBOOKS_DIR.glob("*.md")):
            bundled.append(_describe(path, source="bundled"))
    if _AUTO_DIR.exists():
        for path in sorted(_AUTO_DIR.glob("*.md")):
            auto.append(_describe(path, source="auto"))

    return {
        "bundled": bundled,
        "auto": auto,
        "bundled_count": len(bundled),
        "auto_count": len(auto),
    }


@router.get("/runbook/library/{source}/{filename}")
def runbook_content(source: str, filename: str) -> dict:
    """Read a runbook markdown file. source = bundled | auto."""
    if source == "auto":
        path = _AUTO_DIR / filename
    elif source == "bundled":
        path = _RUNBOOKS_DIR / filename
    else:
        raise HTTPException(status_code=400, detail="source must be 'bundled' or 'auto'")
    if not path.exists() or not path.suffix == ".md":
        raise HTTPException(status_code=404, detail="runbook not found")
    return {"filename": filename, "source": source, "content": path.read_text()}


def _describe(path: Path, *, source: str) -> dict:
    stat = path.stat()
    title = path.stem.replace("_", " ").title()
    text = ""
    try:
        text = path.read_text()
    except Exception:
        pass
    # Pull the first H1 if present
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    return {
        "filename": path.name,
        "title": title,
        "source": source,
        "bytes": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }
