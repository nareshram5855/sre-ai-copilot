# CD Configuration

Continuous deployment configs for GitHub Actions.

## Layout

```
.github/
├── cd/
│   ├── staging.env              # Staging defaults (reference)
│   ├── production.env           # Production defaults (reference)
│   ├── kubernetes/
│   │   └── backend-deployment.yaml
│   └── scripts/
│       └── deploy-k8s.sh
└── workflows/
    ├── ci.yml                   # PR + branch validation
    ├── cd-staging.yml           # Push to staging → GHCR + optional K8s
    └── cd-production.yml        # Push to main → GHCR + optional K8s
```

## Workflows

| Workflow | Trigger | Image tags | GitHub Environment |
|----------|---------|------------|--------------------|
| `cd-staging.yml` | Push to `staging` | `:staging`, `:sha-<commit>` | `staging` |
| `cd-production.yml` | Push to `main` | `:latest`, `:sha-<commit>` | `production` |

Both workflows:
1. Build and push the FastAPI backend image to **GHCR** (`ghcr.io/<owner>/sre-ai-copilot`)
2. Build the React frontend and upload `frontend/dist` as a workflow artifact
3. Optionally deploy to Kubernetes when `KUBE_CONFIG` secret is set

## GitHub setup

### 1. Create Environments

Repo → **Settings → Environments** → create `staging` and `production`.

Optionally add required reviewers on `production`.

### 2. Secrets (per environment or repo-level)

| Secret | Required | Description |
|--------|----------|-------------|
| `KUBE_CONFIG` | Optional | Base64-encoded kubeconfig for cluster deploy |
| `GOOGLE_API_KEY` | Optional | External LLM tier (if enabled) |
| `ANTHROPIC_API_KEY` | Optional | External LLM tier (if enabled) |

`GITHUB_TOKEN` is used automatically for GHCR push (needs `packages: write` — already in workflow).

### 3. Make GHCR package public (optional)

After first push: **Packages → sre-ai-copilot → Package settings → Change visibility**.

## Manual deploy

```bash
# Staging
gh workflow run cd-staging.yml

# Production
gh workflow run cd-production.yml
```

## Local K8s deploy test

```bash
IMAGE=ghcr.io/nareshram5855/sre-ai-copilot:staging
bash .github/cd/scripts/deploy-k8s.sh "$IMAGE"
```
