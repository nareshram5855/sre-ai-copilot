"""
Incident Analysis Agent — structured diagnostic evaluation of raw production incidents.

Accepts any unstructured incident input: stack traces, log blobs, error dumps,
pipeline failures. Returns a streaming structured analysis conforming to the
SRE response schema (Assessment → Pre-impl check → Root Cause → Action Plan).

This fills a distinct gap from rca.py (which takes structured post-incident metadata)
and triage.py (which classifies alert payloads). This agent handles raw paste-in
telemetry from an on-call engineer's terminal.
"""
import asyncio
import json
import logging

import httpx
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["incident-analysis"])

# ── System prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an advanced, autonomous Site Reliability Engineering (SRE) Core Platform Agent. Your primary objective is to ingest real-time runtime exceptions, tracebacks, and pipeline failures, and generate highly precise diagnostic evaluations and structured mitigation steps.

OPERATIONAL CONSTRAINTS:
1. NO CONVERSATIONAL FILLER: Begin output immediately with the incident assessment. No greetings, no "based on the logs" preambles.
2. DETERMINISTIC OUTPUT: Focus exclusively on literal telemetry evidence provided. Never make unbacked assumptions or infer external states not present in the input.
3. SANDBOX ISOLATION: All recommended commands must assume a non-privileged environment. Always provide safe, read-only diagnostic commands before any mutative fix commands.

PRE-IMPLEMENTATION VERIFICATION (mandatory before any fix suggestion):
- Check whether the error is a known pattern (dependency missing, config mismatch, resource exhaustion, network partition, race condition, language/runtime mismatch).
- Check whether a rollback or restart would resolve it before proposing a code change.
- Explicitly state FOUND or NOT FOUND for any existing mitigation path.

You MUST respond using EXACTLY this Markdown structure — no deviations:

## 🚨 Incident Assessment
- **Components Implicated:** [affected services, files, endpoints, infra blocks]
- **Error Paradigm:** [e.g., OOMKilled, CrashLoopBackOff, Dependency Resolution Failure, Runtime Language Mismatch, Config Drift, Network Partition, Deadlock]
- **Severity Signal:** [P1 / P2 / P3 — justify from the telemetry]

## 🔍 Pre-Implementation Capability Check
- **Existing Functionality Status:** [FOUND / NOT FOUND]
- **Codebase Reference:** [If FOUND: exact file and function. If NOT FOUND: describe the gap.]
- **Design Decision:** [Why you call existing code OR why a new fix is strictly necessary.]

## 💡 Root Cause Engine
[Dense engineering analysis. Map each symptom to a specific cause. Cite exact line numbers, exit codes, or log tokens from the provided telemetry. No filler.]

## 🛠️ Execution & Action Plan

### Diagnostic Phase [Read-Only]
```bash
# Safe observation commands — run these first to confirm the hypothesis
```

### Remediation Phase
```bash
# Ordered fix commands — validate each step before proceeding to the next
```

### Validation Phase
```bash
# Post-fix verification — confirm the error condition is cleared
```

## ⚠️ Risk & Blast Radius
- **Impact Scope:** [services/pods/namespaces/users affected]
- **Data Risk:** [None / Read-Only / Write / Potentially Destructive]
- **Estimated MTTR:** [time to resolve if plan is followed]

## 🔁 Rollback Plan
```bash
# Safe rollback commands if remediation worsens the incident
```"""


# ── Request model ──────────────────────────────────────────────────────────────

class IncidentAnalysisPayload(BaseModel):
    raw_incident: str = Field(
        ...,
        min_length=10,
        description="Raw incident data: stack trace, log lines, error output, pipeline failure",
        examples=["ERROR: OOMKilled\n  Pod: auth-service-abc123\n  Namespace: production"]
    )
    service: str = Field(default="", description="Affected service name (optional)")
    environment: str = Field(default="production", examples=["production", "staging"])
    session_id: str = Field(default="default")


# ── Streaming endpoint ─────────────────────────────────────────────────────────

@router.post("/incident/analyze")
async def analyze_incident(payload: IncidentAnalysisPayload) -> StreamingResponse:
    """
    Stream a structured SRE diagnostic analysis of raw incident telemetry.

    SSE event types:
      token  — {text}     streaming markdown token
      done   — {}         analysis complete
      error  — {message}  fatal error
    """
    async def _stream():
        service_ctx = f"Service: {payload.service}\n" if payload.service else ""
        user_message = (
            f"Environment: {payload.environment}\n"
            f"{service_ctx}"
            f"\n--- RAW INCIDENT DATA ---\n"
            f"{payload.raw_incident.strip()}\n"
            f"--- END INCIDENT DATA ---\n\n"
            "Analyze this incident and respond using the required SRE response schema exactly."
        )

        body = {
            "model": settings.ollama_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
            "stream": True,
            "options": {
                "num_ctx":     8192,
                "num_predict": 2048,
                "temperature": 0.05,   # low temp for deterministic diagnostic output
            },
        }

        logger.info(
            "Incident analysis session=%s env=%s service=%r len=%d",
            payload.session_id, payload.environment,
            payload.service or "(unspecified)", len(payload.raw_incident),
        )

        try:
            async with httpx.AsyncClient(timeout=120) as http:
                async with http.stream(
                    "POST",
                    f"{settings.ollama_base_url}/api/chat",
                    json=body,
                ) as resp:
                    async for raw_line in resp.aiter_lines():
                        if not raw_line.strip():
                            continue
                        try:
                            chunk = json.loads(raw_line)
                        except json.JSONDecodeError:
                            continue

                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            yield f"data: {json.dumps({'type': 'token', 'text': token})}\n\n"

                        if chunk.get("done"):
                            yield f"data: {json.dumps({'type': 'done'})}\n\n"
                            return

        except httpx.TimeoutException:
            yield f"data: {json.dumps({'type': 'error', 'message': 'LLM timed out after 120s'})}\n\n"
        except Exception as exc:
            logger.exception("Incident analysis failed: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
