"""Stackport demo mock API — served at /stackport/api/* from the portfolio."""
from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/stackport/api", tags=["stackport-demo"])

# ── Auth ──────────────────────────────────────────────────────────────────────
@router.post("/auth/login")
async def sp_login(request: Request):
    return {"token": "demo-token", "username": "naresh", "role": "admin", "team": "payments"}

@router.get("/auth/me")
async def sp_me():
    return {"username": "naresh", "role": "admin", "team": "payments", "teams": []}

# ── Teams ─────────────────────────────────────────────────────────────────────
@router.get("/teams")
async def sp_teams():
    return {"teams": [
        {"id": 1, "slug": "payments",  "display_name": "Payments",  "github_org": "nareshram5855"},
        {"id": 2, "slug": "platform",  "display_name": "Platform",  "github_org": "nareshram5855"},
        {"id": 3, "slug": "data-eng",  "display_name": "Data Eng",  "github_org": "nareshram5855"},
        {"id": 4, "slug": "fintech",   "display_name": "Fintech",   "github_org": "nareshram5855"},
    ]}

# ── Dashboard ─────────────────────────────────────────────────────────────────
@router.get("/dashboard/github")
async def sp_dashboard():
    return {
        "team": "payments",
        "open_issues": [
            {"id": 1, "title": "feat: add Redis cache layer to payments API", "number": 42, "created_at": "2026-06-03T10:00:00Z"},
            {"id": 2, "title": "feat: scale EKS node group to 5 nodes",       "number": 41, "created_at": "2026-06-02T14:30:00Z"},
            {"id": 3, "title": "fix: RDS backup retention to 30 days (prod)",  "number": 40, "created_at": "2026-06-01T09:00:00Z"},
        ],
        "recent_runs": [
            {"id": "r1", "name": "Terragrunt Plan",  "status": "completed", "conclusion": "success",  "branch": "feat/redis-cache",    "created_at": "2026-06-03T11:00:00Z"},
            {"id": "r2", "name": "Terragrunt Plan",  "status": "completed", "conclusion": "success",  "branch": "feat/eks-scale",      "created_at": "2026-06-02T15:00:00Z"},
            {"id": "r3", "name": "Terragrunt Apply", "status": "completed", "conclusion": "success",  "branch": "main",                "created_at": "2026-06-01T16:00:00Z"},
            {"id": "r4", "name": "Admin Stack Plan", "status": "completed", "conclusion": "success",  "branch": "admin/org-bootstrap", "created_at": "2026-06-02T05:22:00Z"},
            {"id": "r5", "name": "CI",               "status": "completed", "conclusion": "failure",  "branch": "feat/rds-backup",     "created_at": "2026-06-01T08:00:00Z"},
        ],
        "module_count": 43, "blueprint_count": 4, "team_count": 4,
    }

# ── Modules ───────────────────────────────────────────────────────────────────
@router.get("/modules")
async def sp_modules():
    return {"modules": [
        {"id": "networking/vpc",       "category": "networking", "name": "vpc",         "path": "modules/networking/vpc",       "variables": [{"name": "cidr",         "type": "string", "required": True,  "default": None,       "description": "VPC CIDR block"},      {"name": "azs",           "type": "list",   "required": True,  "default": None,  "description": "Availability zones"}, {"name": "single_nat_gateway", "type": "bool", "required": False, "default": "false", "description": "Use single NAT"}]},
        {"id": "networking/alb",       "category": "networking", "name": "alb",         "path": "modules/networking/alb",       "variables": [{"name": "vpc_id",       "type": "string", "required": True,  "default": None,       "description": "VPC ID from vpc module"}]},
        {"id": "networking/cloudfront","category": "networking", "name": "cloudfront",  "path": "modules/networking/cloudfront","variables": [{"name": "default_root_object", "type": "string", "required": False, "default": "index.html", "description": "Default root object"}]},
        {"id": "compute/eks",          "category": "compute",    "name": "eks",         "path": "modules/compute/eks",          "variables": [{"name": "vpc_id",       "type": "string", "required": True,  "default": None,       "description": "VPC ID"},              {"name": "cluster_version", "type": "string", "required": False, "default": "1.29", "description": "Kubernetes version"}]},
        {"id": "compute/ecs",          "category": "compute",    "name": "ecs",         "path": "modules/compute/ecs",          "variables": [{"name": "vpc_id",       "type": "string", "required": True,  "default": None,       "description": "VPC ID"}]},
        {"id": "compute/lambda",       "category": "compute",    "name": "lambda",      "path": "modules/compute/lambda",       "variables": [{"name": "runtime",      "type": "string", "required": False, "default": "python3.12","description": "Lambda runtime"},      {"name": "memory_size",   "type": "number", "required": False, "default": "256",  "description": "Memory in MB"}]},
        {"id": "data/rds",             "category": "data",       "name": "rds",         "path": "modules/data/rds",             "variables": [{"name": "vpc_id",       "type": "string", "required": True,  "default": None,       "description": "VPC ID"},              {"name": "instance_class","type": "string", "required": False, "default": "db.t3.medium", "description": "RDS instance class"}, {"name": "multi_az", "type": "bool", "required": False, "default": "false", "description": "Enable Multi-AZ"}]},
        {"id": "data/elasticache",     "category": "data",       "name": "elasticache", "path": "modules/data/elasticache",     "variables": [{"name": "vpc_id",       "type": "string", "required": True,  "default": None,       "description": "VPC ID"},              {"name": "node_type",     "type": "string", "required": False, "default": "cache.t3.micro", "description": "Cache node type"}]},
        {"id": "data/dynamodb",        "category": "data",       "name": "dynamodb",    "path": "modules/data/dynamodb",        "variables": [{"name": "billing_mode", "type": "string", "required": False, "default": "PAY_PER_REQUEST", "description": "Billing mode"}]},
        {"id": "data/s3",              "category": "data",       "name": "s3",          "path": "modules/storage/s3",           "variables": [{"name": "versioning",   "type": "bool",   "required": False, "default": "false",    "description": "Enable versioning"}]},
        {"id": "security/kms",         "category": "security",   "name": "kms",         "path": "modules/security/kms",         "variables": [{"name": "description",  "type": "string", "required": False, "default": "Platform encryption key", "description": "Key description"}]},
        {"id": "security/iam",         "category": "security",   "name": "iam",         "path": "modules/security/iam",         "variables": [{"name": "trusted_services", "type": "list", "required": False, "default": "[]", "description": "AWS services allowed to assume role"}]},
        {"id": "cicd/ecr",             "category": "cicd",       "name": "ecr",         "path": "modules/cicd/ecr",             "variables": [{"name": "scan_on_push", "type": "bool",   "required": False, "default": "true",     "description": "Scan images on push"}]},
        {"id": "monitoring/cloudwatch","category": "monitoring",  "name": "cloudwatch",  "path": "modules/monitoring/cloudwatch","variables": [{"name": "retention_days","type": "number","required": False, "default": "90",       "description": "Log retention in days"}]},
    ]}

@router.get("/modules/environments")
async def sp_envs():
    return {"environments": [
        {"name": "dev",     "modules": ["networking/vpc","compute/eks","data/rds","data/elasticache","cicd/ecr","security/kms","networking/alb","compute/lambda","data/dynamodb","monitoring/cloudwatch","data/s3","security/iam"]},
        {"name": "staging", "modules": ["networking/vpc","compute/eks","data/rds","cicd/ecr","security/kms","networking/alb","monitoring/cloudwatch"]},
        {"name": "prod",    "modules": ["networking/vpc","compute/eks","data/rds","data/elasticache","cicd/ecr","security/kms","networking/alb","data/dynamodb","monitoring/cloudwatch","data/s3","security/iam","networking/cloudfront"]},
    ]}

# ── Blueprints ────────────────────────────────────────────────────────────────
_BLUEPRINTS = [
    {"id": "eks-app-stack",  "name": "EKS Application Stack",  "category": "compute",    "description": "Production-ready containerised app — VPC, EKS cluster, RDS PostgreSQL, ElastiCache Redis, ECR, ALB.", "tags": ["eks","kubernetes","rds","redis","production"], "compliance": ["sox","pci-ready"], "estimated_cost_min": 180, "estimated_cost_max": 450, "cost_note": "EKS $73 + 2×m5.large $140 + RDS t3.medium $60 + Redis $30", "module_count": 6, "modules": ["networking/vpc","compute/eks","networking/alb","data/rds","data/elasticache","cicd/ecr"], "params": [{"name":"team","label":"Team name","placeholder":"payments","required":True},{"name":"app","label":"App name","placeholder":"payments-api","required":True},{"name":"cidr","label":"VPC CIDR","placeholder":"10.20.0.0/16","required":False}]},
    {"id": "serverless-api", "name": "Serverless API",          "category": "serverless", "description": "Lambda + API Gateway + DynamoDB. Zero servers, auto-scaling, pay-per-request.", "tags": ["lambda","api-gateway","dynamodb","serverless"], "compliance": [], "estimated_cost_min": 5, "estimated_cost_max": 40, "cost_note": "Lambda free tier + API Gateway $3.50/million + DynamoDB on-demand", "module_count": 4, "modules": ["compute/lambda","data/dynamodb","security/kms","cicd/ecr"], "params": [{"name":"team","label":"Team name","placeholder":"checkout","required":True},{"name":"app","label":"App name","placeholder":"checkout-fn","required":True}]},
    {"id": "static-site",    "name": "Static Site",             "category": "static",     "description": "React/Vue/Angular SPA — S3 + CloudFront globally distributed. Automatic HTTPS.", "tags": ["s3","cloudfront","static","cdn"], "compliance": [], "estimated_cost_min": 1, "estimated_cost_max": 15, "cost_note": "S3 < $1 + CloudFront per-request pricing", "module_count": 3, "modules": ["data/s3","networking/cloudfront","security/kms"], "params": [{"name":"team","label":"Team name","placeholder":"frontend","required":True},{"name":"app","label":"App name","placeholder":"marketing-site","required":True}]},
    {"id": "data-platform",  "name": "Data Platform",           "category": "data",       "description": "Kafka (MSK) + S3 data lake + Redshift. Streaming ingestion to analytical query.", "tags": ["msk","kafka","s3","redshift","analytics"], "compliance": ["sox"], "estimated_cost_min": 300, "estimated_cost_max": 800, "cost_note": "MSK 3-broker $220 + Redshift dc2.large $180 + S3 storage", "module_count": 5, "modules": ["networking/vpc","analytics/msk","data/s3","data/dynamodb","security/kms"], "params": [{"name":"team","label":"Team name","placeholder":"data-eng","required":True},{"name":"app","label":"App name","placeholder":"data-lake","required":True}]},
]

@router.get("/blueprints")
async def sp_blueprints():
    return _BLUEPRINTS

@router.get("/blueprints/{bp_id}")
async def sp_blueprint(bp_id: str):
    bp = next((b for b in _BLUEPRINTS if b["id"] == bp_id), None)
    if not bp:
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return bp

@router.post("/blueprints/{bp_id}/render")
async def sp_render(bp_id: str, request: Request):
    bp = next((b for b in _BLUEPRINTS if b["id"] == bp_id), None)
    if not bp:
        return JSONResponse({"detail": "Not found"}, status_code=404)
    body = await request.json()
    params = body.get("params", {})
    team = params.get("team", "demo").replace(" ", "-").lower()
    app_name = params.get("app", "app").replace(" ", "-").lower()
    env = params.get("env", "dev")
    files = [
        {
            "path": f"live/{env}/{mod.split('/')[-1]}/terragrunt.hcl",
            "module": mod,
            "content": f'include "root" {{ path = find_in_parent_folders("root.hcl") }}\n\nterraform {{\n  source = "git::https://github.com/nareshram5855/infra-platform.git//terraform/modules/{mod}?ref=main"\n}}\n\ninputs = {{\n  name = "{team}-{app_name}"\n  env  = "{env}"\n  tags = {{\n    Team      = "{team}"\n    App       = "{app_name}"\n    ManagedBy = "stackport"\n  }}\n}}\n',
        }
        for mod in bp["modules"]
    ]
    return {"blueprint_id": bp_id, "blueprint_name": bp["name"], "team": team, "app": app_name, "env": env, "files": files, "modules": [{"id": m.split("/")[-1], "module": m, "order": i+1} for i,m in enumerate(bp["modules"])]}

# ── History ───────────────────────────────────────────────────────────────────
@router.get("/history")
async def sp_history():
    rows = [
        {"id": 1, "username": "naresh", "action": "deploy.apply", "env": "prod",    "module": "compute/eks",    "status": "success", "created_at": "2026-06-03T11:05:00Z", "details": "payments-api eks cluster applied"},
        {"id": 2, "username": "naresh", "action": "deploy.plan",  "env": "dev",     "module": "data/rds",       "status": "success", "created_at": "2026-06-03T10:00:00Z", "details": "payments rds plan passed"},
        {"id": 3, "username": "priya",  "action": "deploy.plan",  "env": "staging", "module": "networking/vpc", "status": "success", "created_at": "2026-06-02T15:30:00Z", "details": "data-eng vpc plan"},
        {"id": 4, "username": "naresh", "action": "ai.provision", "env": "dev",     "module": None,             "status": "success", "created_at": "2026-06-02T09:00:00Z", "details": "app=payments-api team=payments"},
        {"id": 5, "username": "naresh", "action": "admin.stack.trigger_plan", "env": "admin", "module": None, "status": "success", "created_at": "2026-06-02T05:22:00Z", "details": "branch=admin/org-bootstrap"},
        {"id": 6, "username": "priya",  "action": "deploy.plan",  "env": "staging", "module": "compute/ecs",   "status": "failed",  "created_at": "2026-06-01T14:00:00Z", "details": "ecs plan — missing subnet_ids"},
        {"id": 7, "username": "raj",    "action": "onboard.create","env": "dev",    "module": None,             "status": "success", "created_at": "2026-05-31T10:00:00Z", "details": "project=fintech-api"},
    ]
    return {"deployments": rows, "items": rows, "total": len(rows)}

# ── Admin stack ───────────────────────────────────────────────────────────────
@router.get("/admin/stack")
async def sp_admin_stack():
    return {
        "branch": "admin/org-bootstrap",
        "modules": ["organizational-units","service-control-policies","member-accounts","github-oidc-provider","github-platform-role"],
        "plan_workflow": "admin-stack-plan.yml",
        "compare_url": "https://github.com/nareshram5855/infra-platform/compare/main...admin/org-bootstrap?expand=1",
        "actions_url": "https://github.com/nareshram5855/infra-platform/actions/workflows/admin-stack-plan.yml",
        "org_deploy_actions_url": "https://github.com/nareshram5855/infra-platform/actions/workflows/admin-org-deploy.yml",
        "latest_plan_run": {"status": "completed", "conclusion": "success", "url": "https://github.com/nareshram5855/infra-platform/actions/runs/26800229364", "branch": "admin/org-bootstrap"},
        "latest_org_deploy_run": {"status": "completed", "conclusion": "success", "url": "https://github.com/nareshram5855/infra-platform/actions/runs/26800229364", "branch": "admin/org-bootstrap"},
    }

@router.post("/admin/trigger-github-plan")
async def sp_trigger_plan():
    return {"status": "dispatched", "message": "Demo mode — see github.com/nareshram5855/infra-platform/actions", "actions_url": "https://github.com/nareshram5855/infra-platform/actions"}

@router.post("/admin/trigger-github-deploy")
async def sp_trigger_deploy():
    return {"status": "dispatched", "message": "Demo mode — see github.com/nareshram5855/infra-platform/actions", "actions_url": "https://github.com/nareshram5855/infra-platform/actions"}

# ── AI status (reflects real GOOGLE_API_KEY presence) ─────────────────────────
def _ai_available() -> bool:
    from backend.config import get_settings
    return bool((get_settings().google_api_key or "").strip())

@router.get("/ai/architect/status")
async def sp_ai_status():
    return {"available": _ai_available(), "model": "gemini-2.5-flash", "demo": True}

@router.get("/ai/status")
async def sp_ai_full_status():
    avail = _ai_available()
    return {
        "available": avail,
        "provider": "gemini" if avail else "demo",
        "message": "" if avail else "AI disabled in demo — set GOOGLE_API_KEY on the server",
    }

# ── Users & audit ─────────────────────────────────────────────────────────────
_MOCK_USERS = [
    {"id": 1, "username": "naresh",  "role": "admin",    "teams": [{"team_id": 1, "slug": "payments", "team_role": "team_admin"}],    "created_at": "2026-05-01T09:00:00Z"},
    {"id": 2, "username": "priya",   "role": "operator", "teams": [{"team_id": 2, "slug": "platform", "team_role": "team_operator"}], "created_at": "2026-05-10T11:30:00Z"},
    {"id": 3, "username": "raj",     "role": "viewer",   "teams": [{"team_id": 3, "slug": "data-eng", "team_role": "team_viewer"}],   "created_at": "2026-05-15T14:00:00Z"},
]

_MOCK_AUDIT = [
    {"id": 1, "username": "naresh", "action": "deploy.apply",            "env": "prod",    "module": "compute/eks",    "details": "payments-api EKS cluster applied",      "created_at": "2026-06-03T11:05:00Z"},
    {"id": 2, "username": "naresh", "action": "deploy.plan",             "env": "dev",     "module": "data/rds",       "details": "payments RDS plan passed",              "created_at": "2026-06-03T10:00:00Z"},
    {"id": 3, "username": "priya",  "action": "deploy.plan",             "env": "staging", "module": "networking/vpc", "details": "data-eng VPC plan",                     "created_at": "2026-06-02T15:30:00Z"},
    {"id": 4, "username": "naresh", "action": "ai.provision",            "env": "dev",     "module": None,             "details": "app=payments-api team=payments",         "created_at": "2026-06-02T09:00:00Z"},
    {"id": 5, "username": "naresh", "action": "admin.stack.trigger_plan","env": "admin",   "module": None,             "details": "branch=admin/org-bootstrap",             "created_at": "2026-06-02T05:22:00Z"},
    {"id": 6, "username": "priya",  "action": "deploy.plan",             "env": "staging", "module": "compute/ecs",   "details": "ECS plan — missing subnet_ids",          "created_at": "2026-06-01T14:00:00Z"},
    {"id": 7, "username": "raj",    "action": "onboard.create",          "env": "dev",     "module": None,             "details": "project=fintech-api",                   "created_at": "2026-05-31T10:00:00Z"},
]

@router.get("/users")
async def sp_users():
    return {"users": _MOCK_USERS}

@router.post("/users")
async def sp_create_user(request: Request):
    body = await request.json()
    return {"id": 99, "username": body.get("username", "new-user"), "role": body.get("role", "viewer"), "api_key": "demo-key-shown-once-xxxx", "teams": [], "created_at": "2026-06-25T00:00:00Z"}

@router.post("/users/{user_id}/rotate-key")
async def sp_rotate_key(user_id: int):
    return {"api_key": f"demo-rotated-key-{user_id}-xxxx"}

@router.delete("/users/{user_id}")
async def sp_delete_user(user_id: int):
    return {"deleted": True}

@router.post("/users/{user_id}/teams")
async def sp_assign_team(user_id: int, request: Request):
    return {"ok": True}

@router.delete("/users/{user_id}/teams/{team_id}")
async def sp_remove_team(user_id: int, team_id: int):
    return {"ok": True}

@router.get("/audit")
async def sp_audit(limit: int = 30):
    return {"entries": _MOCK_AUDIT[:limit], "total": len(_MOCK_AUDIT)}

# ── My Team (GitHub workflow runs with full mock data) ─────────────────────────
_MOCK_RUNS = [
    {"id": "r1", "repo": "nareshram5855/infra-platform", "project_id": "p1", "name": "Terragrunt Plan",  "head_branch": "feat/redis-cache",    "status": "completed", "conclusion": "success", "url": "https://github.com/nareshram5855/infra-platform/actions/runs/1", "created_at": "2026-06-03T11:00:00Z"},
    {"id": "r2", "repo": "nareshram5855/infra-platform", "project_id": "p1", "name": "Terragrunt Plan",  "head_branch": "feat/eks-scale",       "status": "completed", "conclusion": "success", "url": "https://github.com/nareshram5855/infra-platform/actions/runs/2", "created_at": "2026-06-02T15:00:00Z"},
    {"id": "r3", "repo": "nareshram5855/infra-platform", "project_id": "p1", "name": "Terragrunt Apply", "head_branch": "main",                 "status": "completed", "conclusion": "success", "url": "https://github.com/nareshram5855/infra-platform/actions/runs/3", "created_at": "2026-06-01T16:00:00Z"},
    {"id": "r4", "repo": "nareshram5855/infra-platform", "project_id": "p1", "name": "Admin Stack Plan", "head_branch": "admin/org-bootstrap",  "status": "completed", "conclusion": "success", "url": "https://github.com/nareshram5855/infra-platform/actions/runs/4", "created_at": "2026-06-02T05:22:00Z"},
    {"id": "r5", "repo": "nareshram5855/infra-platform", "project_id": "p1", "name": "CI",               "head_branch": "feat/rds-backup",      "status": "completed", "conclusion": "failure", "url": "https://github.com/nareshram5855/infra-platform/actions/runs/5", "created_at": "2026-06-01T08:00:00Z"},
]

@router.get("/team/workspace")
async def sp_team():
    return {
        "configured": True,
        "projects": [{"id": "p1", "repo": "nareshram5855/infra-platform", "slug": "infra-platform"}],
        "open_iac_issues_count": 3,
        "failed_runs_count": 1,
        "recent_runs": _MOCK_RUNS[:5],
        "open_iac_issues": [
            {"repo": "nareshram5855/infra-platform", "number": 42, "title": "feat: add Redis cache layer to payments API", "url": "https://github.com/nareshram5855/infra-platform/issues/42"},
            {"repo": "nareshram5855/infra-platform", "number": 41, "title": "feat: scale EKS node group to 5 nodes",      "url": "https://github.com/nareshram5855/infra-platform/issues/41"},
            {"repo": "nareshram5855/infra-platform", "number": 40, "title": "fix: RDS backup retention to 30 days (prod)","url": "https://github.com/nareshram5855/infra-platform/issues/40"},
        ],
        "team": {"id": 1, "slug": "payments", "display_name": "Payments"},
        "members": [
            {"username": "naresh", "role": "admin"},
            {"username": "priya",  "role": "operator"},
            {"username": "raj",    "role": "viewer"},
        ],
    }

@router.get("/team/runs")
async def sp_team_runs(status: str = "all", limit: int = 50):
    runs = _MOCK_RUNS
    if status == "failed":
        runs = [r for r in runs if r.get("conclusion") == "failure"]
    elif status == "success":
        runs = [r for r in runs if r.get("conclusion") == "success"]
    return {"runs": runs[:limit]}

@router.get("/team/runs/{run_id}/detail")
async def sp_run_detail(run_id: str):
    run = next((r for r in _MOCK_RUNS if r["id"] == run_id), None)
    if not run:
        return {"id": run_id, "status": "completed", "conclusion": "success", "jobs": [], "created_at": "2026-06-01T00:00:00Z"}
    is_failure = run["conclusion"] == "failure"
    return {
        "id": run_id,
        "status": run["status"],
        "conclusion": run["conclusion"],
        "created_at": run["created_at"],
        "failed_job":  {"name": "terragrunt-plan"} if is_failure else None,
        "failed_step": {"name": "Run terragrunt plan"} if is_failure else None,
        "log_excerpt": (
            "Error: Failed to init terraform backend\n"
            "  Error: error configuring S3 Backend: AccessDenied: Access Denied\n"
            "  status code: 403, request id: abc123\n\n"
            "Hint: Ensure the IAM role has s3:GetObject on the state bucket."
        ) if is_failure else None,
        "jobs": [
            {
                "id": "j1",
                "name": "terragrunt-plan",
                "steps": [
                    {"number": 1, "name": "Checkout",           "status": "completed", "conclusion": "success"},
                    {"number": 2, "name": "Configure AWS creds", "status": "completed", "conclusion": "success"},
                    {"number": 3, "name": "Setup Terraform",     "status": "completed", "conclusion": "success"},
                    {"number": 4, "name": "Run terragrunt plan", "status": "completed", "conclusion": "failure" if is_failure else "success"},
                ],
            }
        ],
    }

@router.post("/team/runs/{run_id}/ask")
async def sp_run_ask(run_id: str, request: Request):
    """SSE stream: AI explains a failed workflow run."""
    from fastapi.responses import StreamingResponse
    import asyncio, json as _json

    run = next((r for r in _MOCK_RUNS if r["id"] == run_id), None)

    async def _stream():
        if not _ai_available():
            yield "data: AI not configured — set GOOGLE_API_KEY on the server.\n\n"
            yield "data: [DONE]\n\n"
            return
        try:
            from google import genai
            from google.genai import types as _gtypes
            from backend.config import get_settings
            cfg = get_settings()
            client = genai.Client(api_key=cfg.google_api_key)
            log = (
                "Error: Failed to init terraform backend\n"
                "  Error: error configuring S3 Backend: AccessDenied: Access Denied\n"
                "  status code: 403, request id: abc123"
            )
            prompt = f"GitHub Actions workflow '{run['name']}' on branch '{run['head_branch']}' failed.\nLog:\n{log}\nExplain the cause and the exact fix."
            stream = await client.aio.models.generate_content_stream(
                model="gemini-2.5-flash",
                contents=prompt,
                config=_gtypes.GenerateContentConfig(
                    system_instruction="You are a senior SRE. Explain CI/CD failures and provide specific Terraform/AWS fixes.",
                    temperature=0.1, max_output_tokens=512,
                    thinking_config=_gtypes.ThinkingConfig(thinking_budget=0),
                ),
            )
            async for chunk in stream:
                token = chunk.text or ""
                if token:
                    yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            yield f"data: Error: {exc}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

# ── Other pages (skeleton) ────────────────────────────────────────────────────
@router.get("/pipelines")
async def sp_pipelines():       return {"pipelines": []}
@router.get("/pipelines/overview")
async def sp_pipelines_ov():    return {"overview": []}
@router.get("/pipelines/apps")
async def sp_pipelines_apps():  return {"apps": []}
@router.get("/onboard")
async def sp_onboard():         return {"projects": []}
@router.get("/onboard/catalog")
async def sp_onboard_cat():     return {"catalog": []}
