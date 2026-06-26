"""Stackport AI endpoints — served at /api/ai/* for the embedded Stackport demo.

The Stackport frontend (built with VITE_API_BASE=/stackport/api) hardcodes
the streaming AI calls to /api/ai/<path> rather than using VITE_API_BASE,
so these endpoints live at /api/ai on the portfolio backend.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from backend.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["stackport-ai"])


def _ai_available() -> bool:
    return bool((get_settings().google_api_key or "").strip())


async def _gemini_client():
    """Return (client, types) or raise ImportError."""
    from google import genai
    from google.genai import types as _gtypes
    cfg = get_settings()
    return genai.Client(api_key=cfg.google_api_key), _gtypes


# ── Status ─────────────────────────────────────────────────────────────────────

@router.get("/architect/status")
def sp_architect_status():
    return {"available": _ai_available(), "model": "gemini-2.5-flash", "demo": True}


@router.get("/status")
def sp_ai_status():
    avail = _ai_available()
    return {
        "available": avail,
        "provider": "gemini" if avail else "demo",
        "message": "" if avail else "AI disabled in demo — set GOOGLE_API_KEY on the server",
    }


# ── Architecture generation ────────────────────────────────────────────────────

_ARCHITECT_SYSTEM = """You are Stackport AI, an AWS infrastructure architect for a developer platform.

Given requirements in plain English, design an AWS architecture using ONLY these Terraform modules:
- networking/vpc       (VPC + subnets + NAT gateway)
- networking/alb       (Application Load Balancer)
- networking/cloudfront (CloudFront CDN)
- compute/eks          (EKS cluster + managed node groups)
- compute/ecs          (ECS Fargate)
- compute/lambda       (Lambda function)
- data/rds             (RDS PostgreSQL/MySQL, Multi-AZ optional)
- data/elasticache     (ElastiCache Redis)
- data/dynamodb        (DynamoDB, on-demand)
- data/s3              (S3 bucket)
- security/kms         (KMS encryption key)
- security/iam         (IAM role + policies)
- cicd/ecr             (ECR container registry)
- monitoring/cloudwatch (CloudWatch logs + alarms)

Return ONLY valid JSON — no markdown fences, no explanation — matching this exact schema:
{
  "architecture_name": "short descriptive name",
  "summary": "2-3 sentence description",
  "modules": [
    {
      "label": "human-readable name",
      "module": "category/name",
      "deploy_order": 1,
      "reason": "one sentence why",
      "inputs": {"key": "realistic_value"}
    }
  ],
  "security": {
    "sox": true,
    "pci": false,
    "flags": [{"severity": "HIGH|MEDIUM|LOW", "rule": "rule name", "detail": "explanation"}]
  },
  "cost": {
    "min_usd": 50,
    "max_usd": 200,
    "note": "main cost driver",
    "breakdown": ["Service $X/mo"]
  },
  "diagram": {
    "zones": [
      {
        "id": "zone_id",
        "label": "Zone Label",
        "type": "internet|aws_edge|vpc_public|vpc_private|aws_managed",
        "nodes": ["node_id_1", "node_id_2"]
      }
    ],
    "nodes": [
      {"id": "unique_id", "label": "Short Name", "service": "category/module_name"},
      {"id": "user",      "label": "Users",       "service": "user"}
    ],
    "edges": [
      {"from": "id1", "to": "id2", "seq": 1,    "label": "HTTPS",       "dashed": false},
      {"from": "id1", "to": "id2", "seq": null,  "label": "monitors",    "dashed": true}
    ]
  }
}

DIAGRAM RULES — architecturally correct AWS relationships:
Zone types (left to right in diagram):
  internet    — outside AWS (put user here, and any on-prem systems)
  aws_edge    — AWS edge services outside VPC: CloudFront, WAF, Route53, API Gateway, Cognito
  vpc_public  — public subnet inside VPC: ALB, NAT Gateway
  vpc_private — private subnet inside VPC: EKS, ECS, Lambda, RDS, ElastiCache
  aws_managed — AWS-managed services outside VPC: S3, DynamoDB, ECR, CloudWatch, IAM, KMS, SNS, SQS

Correct directional edges (verify every arrow makes real AWS sense):
  User → CloudFront → ALB → EKS/ECS/Lambda    (request flow, sequential, numbered)
  ECR →|image pull| EKS/ECS                   (EKS pulls images FROM ECR, not the other way)
  EKS/Lambda →|writes| RDS/DynamoDB/S3        (app writes to databases/storage)
  KMS →|encrypts| RDS, S3, ElastiCache        (KMS encrypts data at rest)
  CloudWatch -.->|monitors| EKS/RDS/Lambda    (CloudWatch observes — dotted line)
  IAM -.->|authz| EKS/Lambda                  (IAM grants permissions — dotted line)
  SQS/SNS →|triggers| Lambda                  (event-driven patterns)

Rules:
- seq numbers only on primary request-flow edges (happy path 1→2→3…); set null for supporting/platform edges
- dashed:true for observability, IAM, encryption edges; dashed:false for data/request flow
- 6-12 nodes max, every node in exactly one zone
- node labels MUST be the AWS service name only — "ALB", "EKS", "RDS", "CloudFront" — NEVER prefix with app/team name
- For supporting services (IAM, KMS, CloudWatch) only add ONE edge each — do NOT add separate monitor/authz edge per compute and per data node, pick the most important one
- deploy_order in modules: networking first, compute second, data third, platform last
- Always include security/kms when rds/s3/elasticache used; always include monitoring/cloudwatch"""


async def _generate_architecture_stream(requirements: str, app_name: str, team_name: str, env: str):
    import asyncio

    def _sse(event: dict) -> str:
        return f"data: {json.dumps(event)}\n\n"

    if not _ai_available():
        yield _sse({"type": "error", "message": "GOOGLE_API_KEY not configured on the server"})
        return

    yield _sse({"type": "status", "message": "Analysing requirements…"})
    await asyncio.sleep(0)

    try:
        client, _gtypes = await _gemini_client()
    except ImportError:
        yield _sse({"type": "error", "message": "google-genai package not installed on server"})
        return

    prompt = (
        f"Design an AWS architecture for:\n"
        f"App: {app_name}\nTeam: {team_name}\nEnvironment: {env}\n\n"
        f"Requirements: {requirements}"
    )

    yield _sse({"type": "status", "message": "Stackport AI is designing your architecture…"})
    await asyncio.sleep(0)

    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=_gtypes.GenerateContentConfig(
                system_instruction=_ARCHITECT_SYSTEM,
                temperature=0.2,
                max_output_tokens=4096,
                thinking_config=_gtypes.ThinkingConfig(thinking_budget=0),
            ),
        )
        raw = (response.text or "").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

        architecture = json.loads(raw)
        # Attach AWS-style SVG diagram (frontend uses this when available;
        # falls back to Gemini's mermaid which now carries classDef colors)
        try:
            from backend.routers.aws_diagram import generate_aws_svg
            architecture["svg_diagram"] = generate_aws_svg(architecture)
        except Exception as _svg_err:
            logger.warning("SVG generation failed (non-fatal): %s", _svg_err)

        yield _sse({"type": "status", "message": "Architecture designed — rendering…"})
        await asyncio.sleep(0)
        yield _sse({"type": "architecture", "data": architecture})

    except json.JSONDecodeError as exc:
        yield _sse({"type": "error", "message": f"AI returned invalid JSON: {exc}"})
    except Exception as exc:
        logger.exception("Gemini architecture generation failed")
        yield _sse({"type": "error", "message": str(exc)})


@router.post("/architect")
async def sp_architect(request: Request):
    """SSE stream: design AWS architecture from natural language requirements."""
    body = await request.json()
    return StreamingResponse(
        _generate_architecture_stream(
            requirements=body.get("requirements", ""),
            app_name=body.get("app_name", "my-app"),
            team_name=body.get("team_name", "platform"),
            env=body.get("env", "dev"),
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Architecture chat update ───────────────────────────────────────────────────

_UPDATE_SYSTEM = """You are Stackport AI. The user has an existing AWS architecture design and wants to modify it.
Update the architecture JSON based on their request. Return ONLY the complete updated JSON — same schema, no markdown fences."""


@router.post("/architect/update")
async def sp_architect_update(request: Request):
    """Non-streaming: refine existing architecture via chat."""
    if not _ai_available():
        return JSONResponse({"error": "GOOGLE_API_KEY not configured"}, status_code=503)
    try:
        client, _gtypes = await _gemini_client()
    except ImportError:
        return JSONResponse({"error": "google-genai not installed"}, status_code=503)

    body = await request.json()
    architecture = body.get("architecture", {})
    message = body.get("message", "")
    app_name = body.get("app_name", "my-app")
    team_name = body.get("team_name", "platform")
    env = body.get("env", "dev")

    prompt = (
        f"App: {app_name}, Team: {team_name}, Environment: {env}\n\n"
        f"Current architecture:\n{json.dumps(architecture, indent=2)}\n\n"
        f"User request: {message}\n\n"
        f"Return the complete updated architecture JSON."
    )
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=_gtypes.GenerateContentConfig(
                system_instruction=_UPDATE_SYSTEM,
                temperature=0.2,
                max_output_tokens=4096,
                thinking_config=_gtypes.ThinkingConfig(thinking_budget=0),
            ),
        )
        raw = (response.text or "").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            raw = raw.rsplit("```", 1)[0]
        updated = json.loads(raw.strip())
        try:
            from backend.routers.aws_diagram import generate_aws_svg
            updated["svg_diagram"] = generate_aws_svg(updated)
        except Exception as _svg_err:
            logger.warning("SVG generation failed (non-fatal): %s", _svg_err)
        return JSONResponse(updated)
    except Exception as exc:
        logger.exception("Gemini architect update failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Demo provision (streams Terragrunt file events, no real GitHub push) ───────

async def _provision_stream(architecture: dict, app_name: str, team_name: str, env: str):
    import asyncio

    def _sse(event: dict) -> str:
        return f"data: {json.dumps(event)}\n\n"

    modules = sorted(architecture.get("modules", []), key=lambda m: m.get("deploy_order", 99))

    yield _sse({"type": "status", "message": "Generating Terragrunt configs…"})
    await asyncio.sleep(0.1)

    for mod in modules:
        module_id = mod.get("module", "")
        module_name = module_id.split("/")[-1] if "/" in module_id else module_id
        path = f"live/{env}/{module_name}/terragrunt.hcl"
        yield _sse({"type": "file_written", "path": path})
        await asyncio.sleep(0.15)

    yield _sse({"type": "status", "message": "Pushing Terragrunt configs to GitHub…"})
    await asyncio.sleep(0.4)

    branch = f"feat/stackport-{app_name}-{env}"
    pr_url = f"https://github.com/nareshram5855/infra-platform/compare/main...{branch}?expand=1"
    yield _sse({"type": "branch_pushed", "branch": branch, "url": pr_url})
    await asyncio.sleep(0.3)

    yield _sse({"type": "status", "message": "Triggering Terraform plan on GitHub Actions…"})
    await asyncio.sleep(0.5)

    actions_url = "https://github.com/nareshram5855/infra-platform/actions"
    yield _sse({"type": "workflow_result", "url": actions_url})
    yield _sse({"type": "done", "status": "pr_opened"})


@router.post("/provision")
async def sp_provision(request: Request):
    """SSE stream: demo provision — writes Terragrunt HCL and streams progress events."""
    body = await request.json()
    return StreamingResponse(
        _provision_stream(
            architecture=body.get("architecture", {}),
            app_name=body.get("app_name", "my-app"),
            team_name=body.get("team_name", "platform"),
            env=body.get("env", "dev"),
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── AI infrastructure chat ─────────────────────────────────────────────────────

_CHAT_SYSTEM = (
    "You are Stackport AI, an expert AWS infrastructure and DevOps assistant. "
    "Help with Terraform/Terragrunt configs, EKS, RDS, Lambda, S3, IAM, cost optimisation, "
    "and DevOps best practices. Be concise and practical. Use code blocks for configs."
)


async def _chat_stream(question: str, history: list):
    def _sse(text: str) -> str:
        return f"data: {text}\n\n"

    if not _ai_available():
        yield _sse("AI not configured — set GOOGLE_API_KEY on the server.")
        yield _sse("[DONE]")
        return
    try:
        client, _gtypes = await _gemini_client()
    except ImportError:
        yield _sse("google-genai not installed on server.")
        yield _sse("[DONE]")
        return

    try:
        stream = await client.aio.models.generate_content_stream(
            model="gemini-2.5-flash",
            contents=question,
            config=_gtypes.GenerateContentConfig(
                system_instruction=_CHAT_SYSTEM,
                temperature=0.3,
                max_output_tokens=2048,
                thinking_config=_gtypes.ThinkingConfig(thinking_budget=0),
            ),
        )
        async for chunk in stream:
            token = chunk.text or ""
            if token:
                yield _sse(token)
        yield _sse("[DONE]")
    except Exception as exc:
        logger.exception("Gemini chat failed")
        yield _sse(f"Error: {exc}")
        yield _sse("[DONE]")


@router.post("/chat")
async def sp_chat(request: Request):
    """SSE stream: AI infrastructure chat."""
    body = await request.json()
    return StreamingResponse(
        _chat_stream(body.get("question", ""), body.get("history", [])),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Explain Terraform error ────────────────────────────────────────────────────

async def _explain_error_stream(error_output: str, env: str):
    def _sse(text: str) -> str:
        return f"data: {text}\n\n"

    if not _ai_available():
        yield _sse("AI not configured.")
        yield _sse("[DONE]")
        return
    try:
        client, _gtypes = await _gemini_client()
    except ImportError:
        yield _sse("google-genai not installed.")
        yield _sse("[DONE]")
        return

    prompt = (
        f"Environment: {env}\n\n"
        f"Terraform/Terragrunt error:\n{error_output}\n\n"
        f"Explain the root cause and provide a specific fix."
    )
    try:
        stream = await client.aio.models.generate_content_stream(
            model="gemini-2.5-flash",
            contents=prompt,
            config=_gtypes.GenerateContentConfig(
                system_instruction="You are a Terraform/AWS expert. Explain errors clearly with specific actionable fixes.",
                temperature=0.1,
                max_output_tokens=1024,
                thinking_config=_gtypes.ThinkingConfig(thinking_budget=0),
            ),
        )
        async for chunk in stream:
            token = chunk.text or ""
            if token:
                yield _sse(token)
        yield _sse("[DONE]")
    except Exception as exc:
        yield _sse(f"Error: {exc}")
        yield _sse("[DONE]")


@router.post("/explain-error")
async def sp_explain_error(request: Request):
    """SSE stream: explain a Terraform/Terragrunt error."""
    body = await request.json()
    return StreamingResponse(
        _explain_error_stream(body.get("error_output", ""), body.get("env", "dev")),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Review Terraform plan ──────────────────────────────────────────────────────

async def _review_plan_stream(plan_output: str, env: str, module: str):
    def _sse(text: str) -> str:
        return f"data: {text}\n\n"

    if not _ai_available():
        yield _sse("AI not configured.")
        yield _sse("[DONE]")
        return
    try:
        client, _gtypes = await _gemini_client()
    except ImportError:
        yield _sse("google-genai not installed.")
        yield _sse("[DONE]")
        return

    prompt = (
        f"Environment: {env}\nModule: {module}\n\n"
        f"Terraform plan output:\n{plan_output}\n\n"
        f"Review: flag risks, highlight key changes, confirm safe to apply."
    )
    try:
        stream = await client.aio.models.generate_content_stream(
            model="gemini-2.5-flash",
            contents=prompt,
            config=_gtypes.GenerateContentConfig(
                system_instruction="You are a senior SRE reviewing a Terraform plan before apply. Flag prod changes carefully. Be direct about risks.",
                temperature=0.1,
                max_output_tokens=1024,
                thinking_config=_gtypes.ThinkingConfig(thinking_budget=0),
            ),
        )
        async for chunk in stream:
            token = chunk.text or ""
            if token:
                yield _sse(token)
        yield _sse("[DONE]")
    except Exception as exc:
        yield _sse(f"Error: {exc}")
        yield _sse("[DONE]")


@router.post("/review-plan")
async def sp_review_plan(request: Request):
    """SSE stream: AI review of a Terraform plan output."""
    body = await request.json()
    return StreamingResponse(
        _review_plan_stream(
            body.get("plan_output", ""),
            body.get("env", "dev"),
            body.get("module", "unknown"),
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Autofix ────────────────────────────────────────────────────────────────────

@router.post("/autofix")
async def sp_autofix(request: Request):
    """Non-streaming: suggest a fix for a failed deployment."""
    if not _ai_available():
        return JSONResponse({"fix": None, "error": "AI not configured"}, status_code=503)
    try:
        client, _gtypes = await _gemini_client()
    except ImportError:
        return JSONResponse({"fix": None, "error": "google-genai not installed"}, status_code=503)

    body = await request.json()
    error = body.get("error", "")
    env = body.get("env", "dev")
    module = body.get("module", "unknown")

    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=(
                f"Module: {module}\nEnv: {env}\nError:\n{error}\n\n"
                f"Provide a concise fix. Show corrected HCL if it's a config issue. "
                f"If it's AWS credentials/permissions, explain exactly what's missing."
            ),
            config=_gtypes.GenerateContentConfig(
                system_instruction="You are a Terraform/AWS expert. Provide concise, actionable fixes.",
                temperature=0.1,
                max_output_tokens=512,
                thinking_config=_gtypes.ThinkingConfig(thinking_budget=0),
            ),
        )
        return {"fix": response.text or ""}
    except Exception as exc:
        logger.exception("Gemini autofix failed")
        return JSONResponse({"fix": None, "error": str(exc)}, status_code=500)
