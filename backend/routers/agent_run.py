"""
Agentic run-plan endpoint.

Runs commands sequentially, streams live SSE, and on failure automatically
asks the LLM to reason about the error and suggest a fix command.

Security tiers (controlled by full_mode):
  SRE mode  — kubectl/helm/git/docker only
  Full mode — any safe command (mkdir, pip, python, cat, ls, etc.)
"""
import asyncio
import json
import logging
import platform
import re
import shutil

import httpx
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.config import settings
from backend.routers._shell_security import check_command, get_cwd, update_cwd

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["agent"])


class RunPlanRequest(BaseModel):
    commands: list[str]
    task_context: str = ""
    session_id: str = ""
    full_mode: bool = False


# ── Execution ─────────────────────────────────────────────────────────────────

async def _exec(command: str, cwd: str | None, full_mode: bool) -> tuple[list[str], list[str], int]:
    out_lines: list[str] = []
    err_lines: list[str] = []
    try:
        if full_mode:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd or None,
            )
        else:
            import shlex
            try:
                args = shlex.split(command)
            except ValueError as e:
                return [], [f"Parse error: {e}"], -1
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd or None,
            )

        async def _drain(stream, bucket):
            async for raw in stream:
                line = raw.decode(errors="replace").rstrip()
                if line:
                    bucket.append(line)

        await asyncio.gather(_drain(proc.stdout, out_lines), _drain(proc.stderr, err_lines))
        try:
            await asyncio.wait_for(proc.wait(), timeout=120)
        except asyncio.TimeoutError:
            proc.kill()
            err_lines.append("Command timed out after 120 s")
            return out_lines, err_lines, -1
        return out_lines, err_lines, proc.returncode
    except FileNotFoundError:
        tool = command.split()[0]
        return [], [f"'{tool}' not found — is it installed?"], -1
    except Exception as exc:
        return [], [str(exc)], -1


# ── LLM fix reasoning ─────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return {}


# Source-code-in-shell patterns — these can never run directly in bash
_SOURCE_IN_BASH_STDERR = re.compile(
    r"syntax error near unexpected token|"
    r"(from|import|def|class|public|private|protected|package): command not found",
    re.IGNORECASE,
)
_SOURCE_CODE_BODY = re.compile(
    r"^(from\s+\w|import\s+[\w{]|def\s+\w|class\s+\w+[\s:{(]|if\s+__name__|"  # Python
    r"public\s+(class|interface|enum|static|void|\w+\s+\w+)|"                   # Java/Kotlin
    r"private\s+\w|protected\s+\w|package\s+\w+\.\w+|"                         # Java
    r"func\s+\w+\s*\(|type\s+\w+\s+struct|var\s+\w+\s+\w+\s*=)",              # Go
    re.MULTILINE,
)

# Platform-aware package manager
_IS_MAC  = platform.system() == "Darwin"
_PKG_MGR = "brew install" if _IS_MAC else "apt-get install -y"

# Map common tool names to their brew/apt package names when they differ
_TOOL_PKG = {
    "mvn":    ("maven",  "maven"),
    "python":  ("python3", "python3"),
    "pip":     ("python3", "python3-pip"),
    "node":    ("node",  "nodejs"),
    "npm":     ("node",  "npm"),
    "java":    ("openjdk", "default-jdk"),
    "go":      ("go",    "golang"),
    "cargo":   ("rust",  "cargo"),
    "kubectl": ("kubectl", "kubectl"),
    "helm":    ("helm",  "helm"),
    "docker":  ("docker", "docker.io"),
}


def _quick_fix(failed_cmd: str, stderr: str) -> tuple[str, str, str] | None:
    """
    Rule-based error analysis — covers the most common failure modes without LLM.
    Returns (fix_cmd, explanation, root_cause) or None to fall through to LLM.
    """
    # 1. Source code (Python/Java/Go) being run as a shell command
    if _SOURCE_IN_BASH_STDERR.search(stderr) and _SOURCE_CODE_BODY.search(failed_cmd):
        return (
            "",
            "Source code cannot run directly in the shell. "
            "Write it to a file (e.g. cat > app.py << 'EOF' ... EOF) then execute it.",
            "Language mismatch: source code passed to bash instead of a file",
        )

    # 2. sudo requires interactive password
    if re.search(r"sudo: (a password is required|a terminal is required|no tty present)", stderr):
        stripped = re.sub(r"^sudo\s+", "", failed_cmd.strip())
        if stripped != failed_cmd.strip():
            return (
                stripped,
                "Removed sudo — running without elevated privileges",
                "sudo requires an interactive terminal; cannot prompt for password non-interactively",
            )
        return (
            "",
            "sudo requires interactive password — cannot auto-fix in a non-interactive session",
            "sudo password prompt in non-interactive context",
        )

    # 3. Command not found → install via package manager
    not_found = re.search(
        r"(?:bash:|/bin/sh:)\s+(\w[\w.-]*): command not found",
        stderr,
        re.IGNORECASE,
    )
    if not_found:
        tool = not_found.group(1).lower()
        # Ignore shell keywords incorrectly flagged (from Java/Python source lines)
        if tool in {"public", "private", "protected", "import", "from", "def", "class", "package", "func"}:
            return (
                "",
                "Shell is interpreting source code keywords as commands — source code block must not be executed in bash",
                f"Language mismatch: '{tool}' is not a shell command",
            )
        pkg_mac, pkg_linux = _TOOL_PKG.get(tool, (tool, tool))
        pkg = pkg_mac if _IS_MAC else pkg_linux
        install_cmd = f"brew install {pkg}" if _IS_MAC else f"sudo apt-get install -y {pkg}"
        # Verify the tool is already installed (race condition guard)
        if shutil.which(tool):
            return (
                "",
                f"'{tool}' is already installed but not in PATH — try restarting the session or sourcing profile",
                f"'{tool}' found at {shutil.which(tool)} but not on PATH during execution",
            )
        return (
            install_cmd,
            f"Install '{tool}' via {'Homebrew' if _IS_MAC else 'apt-get'}",
            f"'{tool}' is not installed on this system",
        )

    # 4. No such file or directory (path issue)
    no_file = re.search(r"No such file or directory[:\s]+['`]?([^\s'`]+)", stderr)
    if no_file:
        missing = no_file.group(1)
        if "/" in missing:
            parent = "/".join(missing.split("/")[:-1])
            return (
                f"mkdir -p {parent}",
                f"Create the missing directory '{parent}'",
                f"Path '{missing}' does not exist",
            )

    return None  # Fall through to LLM


async def _llm_fix(
    task_context: str,
    failed_cmd: str,
    stderr: str,
    exit_code: int,
    full_mode: bool,
    cwd: str,
) -> tuple[str, str, str]:
    """
    Diagnose a failed command and return a fix.
    Rule-based analysis runs first; LLM is the fallback for unknown errors.
    Returns (fix_command, explanation, root_cause).
    fix_command="" means unfixable — halt and flag for human.
    """
    # Rule-based analysis first — avoids LLM hallucination on well-known errors
    quick = _quick_fix(failed_cmd, stderr)
    if quick is not None:
        return quick

    stderr_short = "\n".join(l for l in stderr.splitlines() if l.strip())[:500]
    platform_note = f"macOS (use 'brew install', NOT apt-get)" if _IS_MAC else "Linux (use apt-get/yum)"
    mode_note = (
        "Any safe shell command is allowed (mkdir, pip, python3, cat, ls, git, docker, kubectl, etc.)."
        if full_mode else
        "Only kubectl/helm/git/docker commands are allowed."
    )

    prompt = f"""A shell command failed. Diagnose and suggest ONE fix command.

SYSTEM: {platform_note}
FAILED COMMAND: {failed_cmd}
WORKING DIRECTORY: {cwd}
EXIT CODE: {exit_code}
ERROR OUTPUT:
{stderr_short}

TASK CONTEXT: {task_context[:300] if task_context else "general operations"}

ALLOWED FIX COMMANDS: {mode_note}

RULES:
1. "syntax error near unexpected token" OR source code keywords (public/private/import/def) as commands → set fix_command="" (language mismatch, cannot fix).
2. "command not found" → install the tool. On macOS use 'brew install <pkg>'. On Linux use 'apt-get install -y <pkg>'. NEVER use apt-get on macOS.
3. "sudo: password required" → strip sudo from the command; run without it.
4. "No such file or directory" → use mkdir -p to create the missing path.
5. fix_command MUST differ from the failed command. If no single-command fix exists, set fix_command="".

Output ONLY valid JSON (no markdown, no prose):
{{"root_cause": "one sentence", "fix_command": "shell command or empty string", "explanation": "one sentence on what changed"}}"""

    try:
        async with httpx.AsyncClient(timeout=45) as client:
            r = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": settings.ollama_model,
                    "messages": [
                        {"role": "system", "content": (
                            "You are an expert shell debugger. Output ONLY a JSON object with "
                            "root_cause, fix_command, and explanation. "
                            "NEVER repeat the failed command as fix_command. "
                            "If the error is 'syntax error near unexpected token', set fix_command to empty string. "
                            "Output ONLY valid JSON — no markdown, no prose."
                        )},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {"num_ctx": 2048, "num_predict": 200, "temperature": 0.0},
                },
            )
            r.raise_for_status()
            data = _extract_json(r.json()["message"]["content"])
            fix_cmd     = (data.get("fix_command") or "").strip()
            explanation = data.get("explanation", "")
            root_cause  = data.get("root_cause", "")

            # Reject if LLM echoed the same command or suggested a syntax-error command
            if fix_cmd and fix_cmd.strip() == failed_cmd.strip():
                fix_cmd     = ""
                explanation = "No safe fix found — fix would repeat the same failing command."
            # Reject if fix still looks like Python source
            if fix_cmd and _SOURCE_CODE_BODY.search(fix_cmd):
                fix_cmd     = ""
                explanation = "Fix contains Python source code — cannot run directly in shell."

            return fix_cmd, explanation, root_cause
    except Exception as exc:
        logger.warning("LLM fix failed: %s", exc)
        return "", f"LLM unavailable: {exc}", "Could not analyse error automatically."


# ── Route ─────────────────────────────────────────────────────────────────────

@router.post("/agent/run-plan")
async def run_plan(body: RunPlanRequest) -> StreamingResponse:
    """
    Execute commands sequentially; auto-debug failures with LLM reasoning.

    SSE event types:
      plan_start   — {total, skipped, cwd, full_mode}
      step_start   — {step, command, cwd, is_fix?}
      stdout/stderr— {step, line, is_fix?}
      step_done    — {step, exit_code, fixed?}
      step_error   — {step, command, exit_code}
      analyzing    — {step, message}
      root_cause   — {step, root_cause}
      fix_applied  — {step, fix_command, explanation}
      fix_blocked  — {step, reason, fix_command}
      no_fix       — {step, explanation}
      plan_done    — {success, succeeded, total}
    """
    async def _stream():
        session_id = body.session_id or "default"
        full_mode  = body.full_mode
        cmds = [c.strip() for c in body.commands if c.strip()]

        runnable, skipped = [], []
        for cmd in cmds:
            ok, reason = check_command(cmd, full_mode)
            (runnable if ok else skipped).append(
                cmd if ok else {"command": cmd, "reason": reason}
            )

        cwd = get_cwd(session_id) if full_mode else None
        yield f"data: {json.dumps({'type':'plan_start','total':len(runnable),'skipped':skipped,'cwd':cwd or '','full_mode':full_mode})}\n\n"

        if not runnable:
            msg = "No commands to run. " + (
                "Enable Full mode to run general shell commands." if not full_mode else "All commands were blocked."
            )
            yield f"data: {json.dumps({'type':'plan_done','success':False,'succeeded':0,'total':0,'message':msg})}\n\n"
            return

        MAX_FIX_ATTEMPTS = 3
        succeeded  = 0
        halted     = False
        halt_step  = None
        halt_reason = ""

        for i, cmd in enumerate(runnable):
            step = i + 1
            current_cwd = get_cwd(session_id) if full_mode else None
            yield f"data: {json.dumps({'type':'step_start','step':step,'command':cmd,'cwd':current_cwd or ''})}\n\n"

            out, err, code = await _exec(cmd, current_cwd, full_mode)

            for line in out:
                yield f"data: {json.dumps({'type':'stdout','step':step,'line':line})}\n\n"
            for line in err:
                yield f"data: {json.dumps({'type':'stderr','step':step,'line':line})}\n\n"

            if full_mode and code == 0:
                update_cwd(session_id, cmd, code, current_cwd or "")

            if code == 0:
                succeeded += 1
                yield f"data: {json.dumps({'type':'step_done','step':step,'exit_code':0})}\n\n"
                continue

            # ── Failed — LLM repair loop (max MAX_FIX_ATTEMPTS attempts) ─────
            yield f"data: {json.dumps({'type':'step_error','step':step,'command':cmd,'exit_code':code})}\n\n"

            last_failed_cmd = cmd
            last_err        = "\n".join(err)
            step_succeeded  = False
            permanent_fail_reason = ""

            for attempt in range(1, MAX_FIX_ATTEMPTS + 1):
                yield f"data: {json.dumps({'type':'analyzing','step':step,'message':f'Analysing error (attempt {attempt}/{MAX_FIX_ATTEMPTS})...'})}\n\n"

                fix_cmd, explanation, root_cause = await _llm_fix(
                    task_context=body.task_context,
                    failed_cmd=last_failed_cmd,
                    stderr=last_err,
                    exit_code=code,
                    full_mode=full_mode,
                    cwd=current_cwd or "",
                )

                yield f"data: {json.dumps({'type':'root_cause','step':step,'root_cause':root_cause})}\n\n"

                if not fix_cmd:
                    permanent_fail_reason = explanation
                    yield f"data: {json.dumps({'type':'no_fix','step':step,'explanation':explanation,'attempts':attempt})}\n\n"
                    break

                ok, reason = check_command(fix_cmd, full_mode)
                if not ok:
                    permanent_fail_reason = reason
                    yield f"data: {json.dumps({'type':'fix_blocked','step':step,'reason':reason,'fix_command':fix_cmd})}\n\n"
                    break

                yield f"data: {json.dumps({'type':'fix_applied','step':step,'fix_command':fix_cmd,'explanation':explanation,'attempt':attempt})}\n\n"
                yield f"data: {json.dumps({'type':'step_start','step':step,'command':fix_cmd,'is_fix':True,'cwd':current_cwd or ''})}\n\n"

                f_out, f_err, f_code = await _exec(fix_cmd, current_cwd, full_mode)
                for line in f_out:
                    yield f"data: {json.dumps({'type':'stdout','step':step,'line':line,'is_fix':True})}\n\n"
                for line in f_err:
                    yield f"data: {json.dumps({'type':'stderr','step':step,'line':line,'is_fix':True})}\n\n"

                if full_mode and f_code == 0:
                    update_cwd(session_id, fix_cmd, f_code, current_cwd or "")

                if f_code == 0:
                    succeeded += 1
                    step_succeeded = True
                    yield f"data: {json.dumps({'type':'step_done','step':step,'exit_code':0,'fixed':True})}\n\n"
                    break

                permanent_fail_reason = f"Fix also failed (exit {f_code})"
                yield f"data: {json.dumps({'type':'step_error','step':step,'command':fix_cmd,'exit_code':f_code,'is_fix':True})}\n\n"
                last_failed_cmd = fix_cmd
                last_err        = "\n".join(f_err)
                code            = f_code

            if not step_succeeded:
                # All repair attempts exhausted — halt the plan, don't continue
                if attempt == MAX_FIX_ATTEMPTS and not permanent_fail_reason:
                    permanent_fail_reason = f"Failed after {MAX_FIX_ATTEMPTS} repair attempts"
                halt_reason = permanent_fail_reason or "Step failed with no recoverable fix"
                halt_step   = step
                halted      = True
                remaining   = len(runnable) - step
                yield f"data: {json.dumps({'type':'plan_halted','step':step,'reason':halt_reason,'remaining':remaining,'succeeded':succeeded,'total':len(runnable)})}\n\n"
                break  # Stop processing further steps

        if not halted:
            yield f"data: {json.dumps({'type':'plan_done','success':succeeded==len(runnable),'succeeded':succeeded,'total':len(runnable)})}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
