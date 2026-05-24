"""
ReAct (Reason + Act) agent endpoint using Ollama native tool calling.

Architecture:
  User question → LLM decides which tool to call → execute tool → feed result back
  → LLM decides next tool → ... → LLM says done → stream final answer

Tools available to the model (mirrors Claude Code's tool set):
  bash_execute   — run a shell command, returns stdout/stderr/exit_code
  write_file     — write content to a file (creates parent dirs automatically)
  read_file      — read a file's content
  list_dir       — list files in a directory

This replaces the fragile "extract commands from markdown prose" approach in agent_run.py.
The model emits structured tool calls; no regex parsing of LLM output needed.
"""
import asyncio
import json
import logging
import os
import re

import ollama
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.config import settings
from backend.routers._shell_security import check_command, get_cwd, update_cwd

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["agent-react"])

MAX_ITERATIONS = 40   # full deploy pipelines need many steps
MAX_TOOL_OUTPUT = 4000  # chars fed back to model per tool result


# ── Tool definitions ──────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash_execute",
            "description": (
                "Execute a shell command and return its stdout, stderr, and exit code. "
                "Use this for any shell operation: creating directories, installing packages, "
                "running scripts, etc. Commands run sequentially in the same working directory."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute. Use && to chain multiple commands."
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file, creating it and any parent directories if needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to the working directory"
                    },
                    "content": {
                        "type": "string",
                        "description": "The complete content to write to the file"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the content of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to the working directory"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and directories at a path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path (default: current working directory)"
                    }
                },
                "required": []
            }
        }
    }
]

SYSTEM_PROMPT = """You are a Full Agent — an autonomous SRE/DevOps assistant that executes tasks end-to-end using tools. You DO NOT stop until the task is fully complete and verified.

EXECUTION LOOP — follow strictly:
1. Break the task into concrete steps
2. Execute EVERY step using tools (bash_execute, write_file, read_file, list_dir)
3. After each tool call, check the output — if it failed, fix it immediately and retry
4. NEVER describe what to do — DO it with a tool call
5. NEVER stop after creating files — always build, run, and verify the result
6. Only give a final summary AFTER all steps are verified successful

COMPLETION CRITERIA — you are NOT done until:
- For Docker tasks: Dockerfile written → image built (docker build) → container runs (docker run) → verified
- For Kubernetes/Minikube tasks: manifests written → applied (kubectl apply) → pods Running (kubectl get pods) → service accessible
- For Flask/app tasks: files written → dependencies installed → app runs without errors
- For any task: the final artifact exists AND works — verify with a tool call

TOOL USAGE RULES:
- Use write_file for any multi-line file content (Dockerfile, app.py, yaml, etc.)
- Use bash_execute for all commands — build, run, test, verify
- After writing a file, always verify it was written: bash_execute("cat <filename>")
- After docker build, run the container to verify it starts
- After kubectl apply, run kubectl get pods/svc to verify deployment

ENVIRONMENT:
- macOS — use brew install, not apt-get
- Prefer python3, pip3
- minikube is available for local Kubernetes
- docker is available

NEVER:
- Stop after writing files without executing them
- Leave the user with "now run these commands yourself"
- Skip verification steps
- Give up after one failure — diagnose and retry with a fix"""


# ── Tool executor ─────────────────────────────────────────────────────────────

async def _exec_tool(
    name: str,
    args: dict,
    session_id: str,
    full_mode: bool,
) -> dict:
    """Execute a tool call and return a result dict for the model."""
    cwd = get_cwd(session_id) if full_mode else None

    if name == "bash_execute":
        command = (args.get("command") or "").strip()
        if not command:
            logger.warning("bash_execute called with empty command — raw args: %r", args)
            return {
                "error": (
                    "ERROR: 'command' argument is missing or empty. "
                    "You MUST provide a command string. "
                    "Example: bash_execute(command='pip3 install flask'). "
                    "Retry with a proper command."
                )
            }

        # Security check
        ok, reason = check_command(command, full_mode)
        if not ok:
            return {"error": f"Command blocked by security policy: {reason}"}

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd or None,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=120)
            except asyncio.TimeoutError:
                proc.kill()
                return {"error": "Command timed out after 120s", "exit_code": -1}

            exit_code = proc.returncode
            stdout = stdout_b.decode(errors="replace").strip()
            stderr = stderr_b.decode(errors="replace").strip()

            if full_mode and exit_code == 0:
                update_cwd(session_id, command, exit_code, cwd or "")

            return {
                "exit_code": exit_code,
                "stdout": stdout[:MAX_TOOL_OUTPUT] if stdout else "",
                "stderr": stderr[:MAX_TOOL_OUTPUT] if stderr else "",
                "cwd": get_cwd(session_id) if full_mode else "",
                "success": exit_code == 0,
            }
        except FileNotFoundError as e:
            return {"error": str(e), "exit_code": -1}
        except Exception as e:
            return {"error": str(e), "exit_code": -1}

    elif name == "write_file":
        path = (args.get("path") or "").strip()
        content = args.get("content", "")
        if not path:
            return {"error": "No file path provided"}

        # Resolve path relative to cwd
        full_path = os.path.join(cwd, path) if cwd else os.path.abspath(path)
        try:
            os.makedirs(os.path.dirname(full_path) or ".", exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"success": True, "path": full_path, "bytes_written": len(content.encode())}
        except Exception as e:
            return {"error": str(e)}

    elif name == "read_file":
        path = (args.get("path") or "").strip()
        if not path:
            return {"error": "No file path provided"}
        full_path = os.path.join(cwd, path) if cwd else os.path.abspath(path)
        try:
            with open(full_path, encoding="utf-8") as f:
                content = f.read()
            return {"content": content[:MAX_TOOL_OUTPUT], "truncated": len(content) > MAX_TOOL_OUTPUT}
        except FileNotFoundError:
            return {"error": f"File not found: {full_path}"}
        except Exception as e:
            return {"error": str(e)}

    elif name == "list_dir":
        path = (args.get("path") or ".").strip()
        full_path = os.path.join(cwd, path) if (cwd and not os.path.isabs(path)) else path
        try:
            entries = os.listdir(full_path)
            return {"entries": sorted(entries), "path": full_path}
        except FileNotFoundError:
            return {"error": f"Directory not found: {full_path}"}
        except Exception as e:
            return {"error": str(e)}

    return {"error": f"Unknown tool: {name}"}


# ── Request / Route ───────────────────────────────────────────────────────────

class ReactRequest(BaseModel):
    question: str
    session_id: str = "default"
    full_mode: bool = False


@router.post("/agent/react")
async def agent_react(body: ReactRequest) -> StreamingResponse:
    """
    ReAct agent: LLM decides what tools to call, we execute them, loop until done.

    SSE event types:
      thinking    — {text}          model's reasoning text before tool calls
      tool_call   — {name, args}    model is calling a tool
      tool_result — {name, result, success}  tool execution result
      text        — {token}         streaming final answer tokens
      done        — {iterations}    agent completed
      error       — {message}       fatal error
    """
    async def _stream():
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": body.question},
        ]

        client = ollama.Client(host=settings.ollama_base_url)
        iteration = 0
        tools_called: set[str] = set()   # names of tools that ran meaningfully
        bash_succeeded = False            # True once a bash command exits 0
        continuations = 0                 # how many times we've re-injected
        MAX_CONTINUATIONS = 3

        while iteration < MAX_ITERATIONS:
            iteration += 1
            logger.info("ReAct iteration %d session=%s", iteration, body.session_id)

            try:
                resp = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: client.chat(
                        model=settings.ollama_model,
                        messages=messages,
                        tools=TOOLS if body.full_mode else [],
                        options={"num_ctx": 8192, "num_predict": 2048, "temperature": 0.1},
                    )
                )
            except Exception as exc:
                yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
                return

            msg = resp.message

            # Pre-tool reasoning text (only emit if more tool calls follow)
            if msg.content and msg.content.strip() and msg.tool_calls:
                yield f"data: {json.dumps({'type': 'thinking', 'text': msg.content.strip()})}\n\n"

            # Append model response to conversation
            messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": msg.tool_calls or []})

            # No tool calls → model wants to stop; check if it's premature
            if not msg.tool_calls:
                wrote_files = "write_file" in tools_called

                # Premature if: files were written but bash never ran successfully
                if wrote_files and not bash_succeeded and continuations < MAX_CONTINUATIONS:
                    # Model wrote files but never built/ran anything — force continuation
                    continuations += 1
                    logger.info(
                        "Premature stop detected (wrote=%s, bash=%s) — injecting continuation %d",
                        wrote_files, ran_bash, continuations,
                    )
                    messages.append({
                        "role": "user",
                        "content": (
                            "You wrote files but haven't executed them yet — task is NOT done. "
                            "Call bash_execute NOW with a real command argument. "
                            "Example: bash_execute(command='pip3 install flask && python3 app.py'). "
                            "You MUST provide the command string inside the tool call. Do it now."
                        ),
                    })
                    continue

                # Truly done — stream the final answer
                if msg.content and msg.content.strip():
                    for token in msg.content.split(" "):
                        yield f"data: {json.dumps({'type': 'text', 'token': token + ' '})}\n\n"
                        await asyncio.sleep(0.01)

                yield f"data: {json.dumps({'type': 'done', 'iterations': iteration})}\n\n"
                return

            # Execute each tool call
            for tc in msg.tool_calls:
                name = tc.function.name
                args = dict(tc.function.arguments) if tc.function.arguments else {}

                yield f"data: {json.dumps({'type': 'tool_call', 'name': name, 'args': args})}\n\n"

                result = await _exec_tool(name, args, body.session_id, body.full_mode)
                success = not result.get("error") and result.get("success", True) is not False

                # Only mark bash as "used" if it actually had a real command
                had_real_command = bool((args.get("command") or "").strip())
                if had_real_command or name != "bash_execute":
                    tools_called.add(name)
                if name == "bash_execute" and success and had_real_command:
                    bash_succeeded = True

                yield f"data: {json.dumps({'type': 'tool_result', 'name': name, 'result': result, 'success': success})}\n\n"

                # Feed result back to model as tool message
                messages.append({
                    "role": "tool",
                    "content": json.dumps(result),
                })

        # Safety cap hit
        yield f"data: {json.dumps({'type': 'error', 'message': f'Agent stopped after {MAX_ITERATIONS} iterations.'})}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
