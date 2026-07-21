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

_ARCHITECT_SYSTEM = """You are Stackport AI, a senior AWS Solutions Architect at a platform engineering company.
Design production-grade AWS architectures following the AWS Well-Architected Framework (6 pillars).

═══════════════════════════════════════════════════════
AVAILABLE TERRAFORM MODULES
═══════════════════════════════════════════════════════
Networking : networking/vpc, networking/alb, networking/cloudfront, networking/waf, networking/apigw, networking/route53
Compute    : compute/eks, compute/ecs, compute/lambda, compute/ec2
Data       : data/rds, data/aurora, data/elasticache, data/dynamodb, data/s3, data/msk
Security   : security/kms, security/iam, security/secrets-manager, security/waf
Observability: monitoring/cloudwatch, monitoring/xray
CICD       : cicd/ecr
Integration: integration/sqs, integration/sns, integration/eventbridge

═══════════════════════════════════════════════════════
COMPLIANCE RULES — STRICTLY ENFORCED
═══════════════════════════════════════════════════════
PCI-DSS  → networking/waf MANDATORY, no public S3 (private + bucket policy), security/kms on ALL data stores
           (RDS/S3/DynamoDB/ElastiCache), security/secrets-manager for DB creds (never env vars),
           monitoring/cloudwatch with CloudTrail audit logs, VPC with private subnets only for compute,
           pci:true in security output
HIPAA    → security/kms on ALL storage, monitoring/cloudwatch with audit logging, VPC private subnets only,
           security/secrets-manager, no public endpoints on data stores, hipaa:true in security output
SOX      → monitoring/cloudwatch + CloudTrail, immutable S3 log bucket, security/iam with least privilege,
           no shared credentials, sox:true in security output
GDPR     → note EU region preference in summary, encryption at rest + in transit mandatory,
           data minimization noted in summary, gdpr:true in security output

═══════════════════════════════════════════════════════
SCALE-TO-SERVICE MAPPING
═══════════════════════════════════════════════════════
small  (<10k req/day)    → compute/lambda + data/dynamodb or data/s3 (serverless-first)
medium (10k–500k/day)    → compute/ecs + data/rds (single-AZ dev, Multi-AZ prod)
large  (500k+/day)       → compute/eks + data/aurora + data/elasticache (Multi-AZ mandatory)
real-time streaming      → integration/msk or integration/sqs + compute/lambda
ML/batch workloads       → compute/ecs + data/s3 + integration/sqs (queue-driven)

═══════════════════════════════════════════════════════
SECURITY DEFAULTS — ALWAYS APPLY
═══════════════════════════════════════════════════════
1. WAF: include networking/waf for ANY internet-facing app (CloudFront or ALB present)
2. KMS: include security/kms whenever rds/aurora/s3/elasticache/dynamodb is used
3. Secrets Manager: include security/secrets-manager whenever compute connects to a database
4. X-Ray: include monitoring/xray for Lambda or ECS/EKS (distributed tracing)
5. Private subnets: ALL compute (EKS/ECS/Lambda/RDS) in vpc_private — NEVER public
6. CloudWatch: ALWAYS include monitoring/cloudwatch with alarms
7. ECR: include cicd/ecr whenever EKS or ECS is used (image registry)

═══════════════════════════════════════════════════════
WELL-ARCHITECTED SCORING GUIDE
═══════════════════════════════════════════════════════
Operational Excellence (0-100): CloudWatch alarms present +20, X-Ray tracing +15, runbook/IaC managed +20, auto-scaling +15, structured logging +10
Security (0-100): WAF present +20, KMS on all stores +20, Secrets Manager +15, private subnets +15, least-privilege IAM +15, no public data endpoints +15
Reliability (0-100): Multi-AZ RDS/Aurora +20, EKS/ECS auto-scaling +15, health checks +10, DLQ on SQS +10, S3 versioning +10, CloudFront failover +15
Performance (0-100): ElastiCache present +20, CloudFront CDN +15, Lambda/ECS right-sized +15, Aurora read replicas +15, DynamoDB DAX +10, async SQS decoupling +15
Cost Optimization (0-100): serverless-first +15, reserved capacity noted +10, S3 lifecycle +10, right-sized instances +15, DynamoDB on-demand +10, spot/Fargate Spot +10
Sustainability (0-100): serverless components +20, managed services (no self-managed) +20, right-sizing documented +15, auto-scale-to-zero capable +15, Graviton ARM noted +10

═══════════════════════════════════════════════════════
OUTPUT SCHEMA — return ONLY valid JSON, no markdown
═══════════════════════════════════════════════════════
{
  "architecture_name": "concise descriptive name",
  "summary": "3-4 sentences: what it does, key design decisions, why these services were chosen",
  "modules": [
    {
      "label": "human-readable name",
      "module": "category/name",
      "deploy_order": 1,
      "reason": "one sentence — reference the actual requirement it addresses",
      "inputs": {"key": "realistic_value_not_placeholder"}
    }
  ],
  "security": {
    "sox":   false,
    "pci":   false,
    "hipaa": false,
    "gdpr":  false,
    "flags": [{"severity": "CRITICAL|HIGH|MEDIUM|LOW", "rule": "name", "detail": "specific explanation"}]
  },
  "cost": {
    "min_usd": 50,
    "max_usd": 200,
    "note": "primary cost driver sentence",
    "breakdown": ["ECS Fargate 2 vCPU: ~$60/mo", "RDS t3.medium Multi-AZ: ~$80/mo"]
  },
  "well_architected": {
    "operational_excellence": {"score": 75, "notes": "CloudWatch alarms configured; add X-Ray for full tracing"},
    "security":               {"score": 90, "notes": "WAF + KMS + Secrets Manager — excellent posture"},
    "reliability":            {"score": 70, "notes": "Multi-AZ RDS; consider ECS auto-scaling policy"},
    "performance":            {"score": 65, "notes": "Add ElastiCache Redis to reduce RDS read latency"},
    "cost_optimization":      {"score": 80, "notes": "Fargate Spot for dev workloads would cut costs 70%"},
    "sustainability":         {"score": 70, "notes": "Managed services used; consider Graviton2 for ECS"}
  },
  "diagram": {
    "zones": [
      {"id": "internet",     "label": "Internet",      "type": "internet",     "nodes": ["user"]},
      {"id": "edge",         "label": "AWS Edge",       "type": "aws_edge",    "nodes": ["waf", "cf"]},
      {"id": "vpc_pub",      "label": "VPC Public",     "type": "vpc_public",  "nodes": ["alb"]},
      {"id": "vpc_priv",     "label": "VPC Private",    "type": "vpc_private", "nodes": ["ecs", "rds"]},
      {"id": "aws_managed",  "label": "AWS Managed",    "type": "aws_managed", "nodes": ["s3", "cw", "kms"]}
    ],
    "nodes": [
      {"id": "user", "label": "Users",      "service": "user"},
      {"id": "waf",  "label": "WAF",        "service": "security/waf"},
      {"id": "cf",   "label": "CloudFront", "service": "networking/cloudfront"}
    ],
    "edges": [
      {"from": "user", "to": "waf",  "seq": 1,    "label": "HTTPS",    "dashed": false},
      {"from": "waf",  "to": "cf",   "seq": 2,    "label": "filtered", "dashed": false},
      {"from": "cw",   "to": "ecs",  "seq": null, "label": "monitors", "dashed": true}
    ]
  }
}

═══════════════════════════════════════════════════════
DIAGRAM RULES
═══════════════════════════════════════════════════════
Zone order (left → right): internet → aws_edge → vpc_public → vpc_private → aws_managed

Zone membership:
  internet    : Users, on-prem systems, external APIs
  aws_edge    : CloudFront, WAF, Route53, API Gateway, Cognito (outside VPC)
  vpc_public  : ALB, NAT Gateway (public subnet)
  vpc_private : EKS, ECS, Lambda, RDS, Aurora, ElastiCache, Secrets Manager (private subnet)
  aws_managed : S3, DynamoDB, ECR, CloudWatch, X-Ray, IAM, KMS, SQS, SNS, EventBridge, MSK

Edge rules:
  seq 1,2,3... → primary request path ONLY (user → edge → compute → data)
  seq null     → all supporting edges (monitoring, auth, encryption, CI/CD)
  dashed:false → data/request flow (solid arrow)
  dashed:true  → CloudWatch monitors, X-Ray traces, KMS encrypts, IAM authorizes, ECR pulls
  WAF arrow    → solid (it IS in the request path, not a side-channel)
  ECR → EKS/ECS → dashed (image pull is a platform concern, not a user request)

Quantity limits:
  6–12 nodes total; every node in EXACTLY one zone
  Supporting services (KMS, IAM, CloudWatch, X-Ray): ONE dashed edge each to primary compute node
  Never add duplicate monitoring edges to every node — pick the most important target

Label rules:
  Node labels: AWS service name ONLY — "WAF", "ALB", "EKS", "Aurora" — NEVER app-prefixed
  Edge labels: short verb phrase — "HTTPS", "queries", "monitors", "encrypts", "triggers"

Deploy order: networking(1-3) → security/iam(4-5) → compute(6-8) → data(9-11) → observability(12-14)
Always include: security/kms when any data store present; monitoring/cloudwatch always; networking/waf for internet-facing"""


async def _generate_architecture_stream(
    requirements: str,
    app_name: str,
    team_name: str,
    env: str,
    scale: str = "",
    compliance: list | None = None,
    patterns: list | None = None,
    rag_context: str = "",
):
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

    # Build structured prompt
    compliance_str = ", ".join(compliance) if compliance else "none specified"
    patterns_str   = ", ".join(patterns)   if patterns   else "standard"
    scale_str      = scale or "not specified — infer from requirements"

    prompt_parts = [
        f"Design an AWS architecture for the following application:",
        f"",
        f"App Name   : {app_name}",
        f"Team       : {team_name}",
        f"Environment: {env}",
        f"Scale      : {scale_str}",
        f"Compliance : {compliance_str}",
        f"Patterns   : {patterns_str}",
        f"",
        f"Requirements:",
        f"{requirements}",
    ]
    if rag_context:
        prompt_parts += [
            f"",
            f"Reference architectures from AWS best practices (use as guidance, not copy-paste):",
            f"{rag_context}",
        ]
    prompt = "\n".join(prompt_parts)

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

    # Phase B: attempt RAG context retrieval (non-fatal if unavailable)
    rag_context = ""
    try:
        from backend.rag.aws_retriever import retrieve_aws_patterns
        rag_context = retrieve_aws_patterns(
            query=body.get("requirements", ""),
            compliance=body.get("compliance", []),
            scale=body.get("scale", ""),
            patterns=body.get("patterns", []),
        )
    except Exception:
        pass  # RAG optional — generation works without it

    return StreamingResponse(
        _generate_architecture_stream(
            requirements=body.get("requirements", ""),
            app_name=body.get("app_name", "my-app"),
            team_name=body.get("team_name", "platform"),
            env=body.get("env", "dev"),
            scale=body.get("scale", ""),
            compliance=body.get("compliance", []),
            patterns=body.get("patterns", []),
            rag_context=rag_context,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Phase C: Clarifying questions ─────────────────────────────────────────────

_CLARIFY_SYSTEM = """You are Stackport AI. A user wants to design an AWS architecture and has provided a brief description.
Identify 2–4 clarifying questions that would help you design a significantly better, more specific architecture.
Focus on: scale/traffic, compliance requirements, existing infrastructure, latency sensitivity, team's AWS experience.
Return ONLY valid JSON: {"questions": ["question 1", "question 2", "question 3"]}
If the description is already very detailed (>50 words with specific tech choices), return {"questions": []} — no questions needed."""


@router.post("/architect/clarify")
async def sp_architect_clarify(request: Request):
    """Return 2-4 clarifying questions for the user's requirements."""
    if not _ai_available():
        return JSONResponse({"questions": []})
    try:
        client, _gtypes = await _gemini_client()
    except ImportError:
        return JSONResponse({"questions": []})

    body = await request.json()
    requirements = body.get("requirements", "")

    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"User requirements: {requirements}",
            config=_gtypes.GenerateContentConfig(
                system_instruction=_CLARIFY_SYSTEM,
                temperature=0.3,
                max_output_tokens=512,
                thinking_config=_gtypes.ThinkingConfig(thinking_budget=0),
            ),
        )
        raw = (response.text or "").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            raw = raw.rsplit("```", 1)[0]
        data = json.loads(raw.strip())
        return JSONResponse({"questions": data.get("questions", [])})
    except Exception:
        return JSONResponse({"questions": []})


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
