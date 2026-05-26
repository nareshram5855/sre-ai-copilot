"""
Command execution endpoint — runs CLI commands and streams output as SSE.

Security tiers (controlled by full_mode flag in request):
  SRE mode  (default) — kubectl/helm/git/docker only, strict allowlist
  Full mode           — any command except catastrophic ops (rm -rf /, format disk, etc.)
                        Equivalent to Claude Code's terminal capability.

All executions are audit-logged. Working directory tracked per session.
"""
import asyncio
import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.memory.audit_store import log_execution_audit
from backend.routers._security import require_api_key
from backend.routers._shell_security import check_command, get_cwd, update_cwd

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["execute"])


class ExecuteRequest(BaseModel):
    command: str
    session_id: str = ""
    cwd: str = ""
    full_mode: bool = False


@router.post("/chat/execute", dependencies=[Depends(require_api_key)])
async def execute_command(body: ExecuteRequest) -> StreamingResponse:
    """
    Execute a command and stream stdout/stderr as SSE.

    SRE mode  (full_mode=False): kubectl/helm/git/docker allowlist
    Full mode (full_mode=True):  any safe command — mkdir, pip, python, cat, ls, etc.

    Event types:
      {"type": "allowed",  "command": "...", "cwd": "..."}
      {"type": "stdout",   "line": "..."}
      {"type": "stderr",   "line": "..."}
      {"type": "done",     "exit_code": N}
      {"type": "error",    "message": "..."}
    """
    command = body.command.strip()
    session_id = body.session_id or "default"

    async def _stream():
        allowed, reason = check_command(command, body.full_mode)
        if not allowed:
            log_execution_audit(
                execution_id=session_id,
                action_type="shell_execute",
                tool_name="shell",
                command_details={"command": command, "full_mode": body.full_mode},
                status="denied",
                error=reason,
            )
            yield f"data: {json.dumps({'type': 'error', 'message': reason})}\n\n"
            return

        cwd = get_cwd(session_id) if body.full_mode else None
        logger.info("EXECUTE mode=%s session=%s cwd=%s cmd=%r",
                    "full" if body.full_mode else "sre", session_id, cwd, command)
        yield f"data: {json.dumps({'type': 'allowed', 'command': command, 'cwd': cwd or ''})}\n\n"

        try:
            if body.full_mode:
                # Full mode: shell=True so &&, pipes, cd all work naturally
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                )
            else:
                import shlex
                try:
                    args = shlex.split(command)
                except ValueError as e:
                    yield f"data: {json.dumps({'type': 'error', 'message': f'Parse error: {e}'})}\n\n"
                    return
                proc = await asyncio.create_subprocess_exec(
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

            async def _read(stream, kind: str):
                async for raw in stream:
                    line = raw.decode(errors="replace").rstrip()
                    if line:
                        yield f"data: {json.dumps({'type': kind, 'line': line})}\n\n"

            async def _drain():
                async for ev in _read(proc.stdout, "stdout"):
                    yield ev
                async for ev in _read(proc.stderr, "stderr"):
                    yield ev

            async for ev in _drain():
                yield ev

            try:
                await asyncio.wait_for(proc.wait(), timeout=120)
            except asyncio.TimeoutError:
                proc.kill()
                yield f"data: {json.dumps({'type': 'error', 'message': 'Command timed out (120s)'})}\n\n"
                return

            if body.full_mode:
                update_cwd(session_id, command, proc.returncode, cwd or "")

            yield f"data: {json.dumps({'type': 'done', 'exit_code': proc.returncode})}\n\n"
            log_execution_audit(
                execution_id=session_id,
                action_type="shell_execute",
                tool_name="shell",
                command_details={"command": command, "full_mode": body.full_mode, "cwd": cwd or ""},
                status="success" if proc.returncode == 0 else "error",
                error="" if proc.returncode == 0 else f"exit_code={proc.returncode}",
            )
            logger.info("EXECUTE done exit=%d cmd=%r", proc.returncode, command)

        except FileNotFoundError:
            tool = command.split()[0]
            yield f"data: {json.dumps({'type': 'error', 'message': f'{tool!r} not found — is it installed?'})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
