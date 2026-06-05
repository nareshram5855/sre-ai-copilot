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

# ── AI (disabled in demo) ─────────────────────────────────────────────────────
@router.get("/ai/architect/status")
async def sp_ai_status():
    return {"available": False, "model": "gemini-2.5-flash-lite", "demo": True}

@router.get("/ai/status")
async def sp_ai_full_status():
    return {"available": False, "provider": "demo", "message": "AI disabled in demo — see github.com/nareshram5855/infra-platform"}

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
@router.get("/users")
async def sp_users():           return {"users": [{"id":1,"username":"naresh","role":"admin"},{"id":2,"username":"priya","role":"operator"},{"id":3,"username":"raj","role":"viewer"}]}
@router.get("/audit")
async def sp_audit():           return {"items": [], "total": 0}
@router.get("/team/workspace")
async def sp_team():            return {"team": {"id":1,"slug":"payments","display_name":"Payments"},"members":[{"username":"naresh","role":"admin"},{"username":"priya","role":"operator"},{"username":"raj","role":"viewer"}],"recent_runs":[],"open_issues":[]}
