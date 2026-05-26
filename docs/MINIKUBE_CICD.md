# Minikube CI/CD on MacBook

Deploy the SRE AI Copilot data stack to local Minikube via a **self-hosted GitHub Actions runner** on the same Mac. GitHub-hosted runners cannot reach your Minikube cluster; the runner must live on the MacBook where Minikube runs.

Target workspace path: `/Users/shivapriya/Downloads/sre-ai`

---

## What gets deployed

| Component | Namespace | Notes |
|-----------|-----------|-------|
| Prometheus, Loki, Promtail, OTel | `observability` | Metrics + logs for Observe page |
| Synthetic demo apps | `synthetic` | auth-service, order-service |
| Kafka | `kafka` | Topics `sre.incidents.triage`, `sre.observability.anomalies` |
| Redis | `default` | Optional persistence layer |
| ChromaDB | `sre-ai` | Vector store |
| Backend (optional) | `sre-ai` | Off by default — see hybrid mode |

Workflow file: [`.github/workflows/cd-minikube-mac.yml`](../.github/workflows/cd-minikube-mac.yml)

One-command local equivalent:

```bash
make deploy-all          # runs infrastructure/k8s/deploy-all.sh
make smoke-test-minikube # post-deploy checks
```

---

## Hybrid dev mode (default)

The CD workflow deploys **infrastructure in Minikube** but leaves the **FastAPI backend on the host**:

```bash
make dev-up                       # after sleep/restart — refresh :19090 Prometheus, :13100 Loki
make observability-port-forward   # same port-forward step as dev-up
make kafka-port-forward           # :9092
make start-backend                # :8080 (auto-runs port-forward ensure on start)
```

**After Mac sleep or minikube restart**, stale `kubectl port-forward` processes are the #1 cause of Command Center showing Prometheus/Loki DOWN with 0 service instances. Run `make dev-up` before opening the UI.

Optional watchdog (restarts port-forwards if they die):

```bash
make observability-port-forward-watch   # foreground loop, Ctrl+C to stop
```

This matches daily `make` dev flow and avoids building/pushing images on every push. Smoke tests warn (not fail) if `:8080/health` is offline unless you enable **strict backend smoke** in `workflow_dispatch`.

To deploy backend **inside** Minikube, run the workflow manually with **Deploy backend container into Minikube** enabled, or locally:

```bash
DEPLOY_BACKEND=true infrastructure/k8s/deploy-all.sh
```

---

## Prerequisites

On the MacBook:

```bash
brew install minikube kubectl docker gh
minikube start --cpus=4 --memory=8192
```

Optional host services (not deployed by CD):

- **Ollama** — `ollama serve` (LLM on Metal GPU)
- **Backend** — `make start-backend` (hybrid mode)
- **Frontend** — `make start-frontend` (local Vite dev server)

---

## Self-hosted runner setup

### Option A — helper script

From the repo root:

```bash
chmod +x scripts/setup-github-runner-mac.sh
./scripts/setup-github-runner-mac.sh YOUR_GITHUB_ORG/sre-ai macbook-minikube
```

The script:

1. Downloads the macOS Actions runner
2. Registers with labels: `self-hosted`, `macOS`, `minikube`
3. Installs a `launchd` service (`./svc.sh install`)

### Option B — manual setup

1. GitHub → **Settings → Actions → Runners → New self-hosted runner**
2. Choose **macOS** / **ARM64**
3. Download and extract the runner in e.g. `~/actions-runners/macbook-minikube`
4. Configure:

```bash
./config.sh \
  --url https://github.com/YOUR_ORG/sre-ai \
  --token YOUR_REGISTRATION_TOKEN \
  --name macbook-minikube \
  --labels self-hosted,macOS,minikube \
  --unattended
```

5. Install as a service:

```bash
sudo ./svc.sh install
sudo ./svc.sh start
```

6. Confirm the runner appears **Idle** with labels `macOS` and `minikube`.

### Runner user and Minikube

The runner service runs as your macOS user. Start Minikube once as that user:

```bash
minikube start --cpus=4 --memory=8192
minikube status
```

Ensure `kubectl config current-context` is `minikube`.

---

## Triggering a deploy

### GitHub UI

**Actions → CD — Minikube (MacBook) → Run workflow**

Optional inputs:

| Input | Default | Purpose |
|-------|---------|---------|
| Deploy backend in cluster | `false` | Build `sre-ai-backend:local` in Minikube Docker |
| Skip synthetic | `false` | Skip demo app image build (faster) |
| Strict backend smoke | `false` | Fail if host backend not on `:8080` |

### Automatic

Pushes to **`develop`** also trigger the workflow (disable by removing the `push` block in the workflow YAML).

### CLI

```bash
gh workflow run cd-minikube-mac.yml --ref develop
gh run list --workflow=cd-minikube-mac.yml
gh run watch
```

---

## Secrets

**None required** for the default Minikube CD workflow.

| Secret | When needed |
|--------|-------------|
| *(none)* | Hybrid deploy — cluster + smoke only |
| `GITHUB_TOKEN` | Auto-provided; not used by this workflow |
| Cloud `KUBE_CONFIG` | Only for [cd-staging.yml](../.github/workflows/cd-staging.yml) / [cd-production.yml](../.github/workflows/cd-production.yml) |

Do **not** commit `.env`, kubeconfig, or registration tokens.

---

## Workflow steps

1. **Checkout** — fresh clone in runner workspace (`$GITHUB_WORKSPACE`)
2. **Verify toolchain** — `minikube`, `kubectl`, `docker`
3. **Deploy** — `infrastructure/k8s/deploy-all.sh` (idempotent `kubectl apply` + rollout wait)
4. **Smoke test** — `infrastructure/k8s/smoke-test.sh` (pods, NodePorts, Redis, ChromaDB, Kafka topics)
5. **Summary** — pod list in job summary

---

## Local validation (no GitHub)

```bash
chmod +x infrastructure/k8s/deploy-all.sh infrastructure/k8s/smoke-test.sh
infrastructure/k8s/deploy-all.sh
infrastructure/k8s/smoke-test.sh
```

Skip synthetic for a quicker run:

```bash
SKIP_SYNTHETIC=true infrastructure/k8s/deploy-all.sh
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Command Center: Prometheus/Loki DOWN, 0 instances, SLO no data | `make dev-up` (kills stale port-forwards, restarts :19090/:13100) |
| Job queued forever | Runner offline or missing `macOS` / `minikube` labels |
| `minikube status` fails | `minikube start` as the runner user |
| Synthetic build slow | Re-run with **Skip synthetic** |
| Backend smoke warning | Expected in hybrid mode; start `make start-backend` or enable in-cluster backend |
| Redis exec fails | `kubectl get pods -l app=sre-ai-redis` — re-run `deploy-all` |

---

## Related files

- `infrastructure/k8s/deploy-all.sh` — unified deploy entrypoint
- `infrastructure/k8s/smoke-test.sh` — CI smoke checks
- `scripts/setup-github-runner-mac.sh` — runner bootstrap
- `scripts/ensure-port-forwards.sh` — idempotent port-forward refresh + optional `--loop` watchdog
- `Makefile` — `dev-up`, `deploy-all`, `smoke-test-minikube` targets

Cloud CD workflows (`cd-staging`, `cd-production`) are unchanged.
