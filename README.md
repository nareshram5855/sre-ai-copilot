# SRE AI Copilot

> Local LLM-powered Site Reliability Engineering platform.
> No external APIs required. Runs entirely on your machine.

---

## What It Does

Five SRE capabilities powered by a local LLM + RAG pipeline over your own runbooks and incident history:

| Feature | Status | Description |
|---|---|---|
| Intelligent Alert Triage | ✅ Phase 1 | RAG retrieves similar past incidents → LLM classifies P1/P2/P3 with confidence score |
| On-Call Knowledge Assistant | ✅ Phase 2 | Natural language Q&A over runbooks — answers with exact commands (ChatWidget) |
| Autonomous Runbook Executor | ✅ Phase 2 | LangGraph ReAct loop with kubectl tools and human approval gates |
| Auto RCA Generator | ✅ Phase 2 | Collects incident timeline → LLM writes full RCA |
| Supervisor Agent | ✅ Phase 2 | Single `/api/v1/ask` entry point — classifies intent and routes to specialist |
| Incident Analysis | ✅ Phase 2 | Live Prometheus/Loki telemetry analysis + synthetic demo stack |
| Voice Input (optional) | ✅ Plugin | STT via Whisper — enable with `VOICE_VOICE_ENABLED=true` |
| Proactive Anomaly Predictor | 🔧 Phase 3 | Monitors Prometheus metrics continuously, creates tickets before outages |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        React Frontend                        │
│              Alert Panel │ Chat Interface                    │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP (localhost:5173 → :8080)
┌──────────────────────────▼──────────────────────────────────┐
│                      FastAPI Backend                         │
│   routers/           agents/           llm/                  │
│   ├─ health.py       ├─ base.py        ├─ router.py          │
│   ├─ triage.py       └─ triage_agent.py└─ sanitizer.py      │
│   └─ knowledge.py                                            │
└──────┬───────────────────┬─────────────────────────────────┘
       │                   │
       ▼                   ▼
┌─────────────┐   ┌────────────────────────────────────────────┐
│  ChromaDB   │   │           LLM Routing Layer                │
│  (Minikube) │   │                                            │
│             │   │  Complexity  →  Tier  →  Model             │
│  incidents  │   │  ─────────────────────────────────         │
│  runbooks   │   │  LOW         LOCAL    Mistral 7B  ($0)     │
│  architecture│  │  MEDIUM      STANDARD Gemini Flash ($0.11) │
└─────────────┘   │  HIGH        ADVANCED Claude Haiku ($2.40) │
       ▲          │  CRITICAL    PREMIUM  Claude Sonnet ($9)   │
       │          │                                            │
       │          │  • Data sanitized before any external call  │
       │          │  • Every external call audit-logged         │
       │          │  • allow_external_llm=false by default      │
┌──────┴──────┐   └────────────────┬───────────────────────────┘
│  Embeddings │                    │
│  nomic-     │            ┌───────▼──────────────────┐
│  embed-text │            │   Ollama (native macOS)   │
│  (Ollama)   │            │   Mistral 7B Q4_K_M       │
└─────────────┘            │   Metal GPU acceleration  │
                           └──────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| LLM Runtime | Ollama (native macOS) | Metal GPU — 3x faster than Docker on Apple Silicon |
| Primary Model | Mistral 7B Q4_K_M | Best quality/size ratio for structured JSON output |
| Embeddings | nomic-embed-text | 768-dim, reuses Ollama process, ~200ms per batch |
| LLM Escalation | Gemini Flash / Claude Haiku / Claude Sonnet | Tiered cost — pay only for genuinely complex problems |
| RAG Framework | LangChain LCEL | Composable chains, clean separation of retrieval and generation |
| Vector Store | ChromaDB | Runs in Minikube (same manifests → EKS in Phase 4) |
| Backend | FastAPI + Python 3.11 | Async, auto OpenAPI docs, Prometheus instrumentation built-in |
| Frontend | React 18 + Vite + TailwindCSS | HMR, dark theme, minimal bundle |
| Infra (local) | Minikube + kubectl | Manifests are the direct foundation for Helm charts in Phase 4 |
| Infra (prod) | EKS + Terraform + ArgoCD + Helm | Phase 4 |

---

## Project Structure

```
sre-ai-copilot/
├── backend/
│   ├── agents/
│   │   ├── base.py             ← BaseAgent: LLM routing, RAG, timing, error handling
│   │   └── triage_agent.py     ← Phase 1: alert severity classification
│   ├── llm/
│   │   ├── router.py           ← complexity scorer + LLM factory + audit logger
│   │   └── sanitizer.py        ← strips hostnames/IPs/credentials before external calls
│   ├── rag/
│   │   ├── embeddings.py       ← nomic-embed-text via Ollama
│   │   ├── ingestor.py         ← markdown → chunks → ChromaDB
│   │   └── retriever.py        ← similarity search with scores
│   ├── routers/
│   │   ├── _models.py          ← shared Pydantic schemas
│   │   ├── health.py
│   │   ├── triage.py
│   │   └── knowledge.py
│   ├── knowledge/
│   │   ├── incidents/          ← past incident markdown files (IAM/CISO domain)
│   │   ├── runbooks/           ← operational runbooks
│   │   └── architecture/       ← system architecture docs
│   ├── config.py               ← all settings + knowledge collection registry
│   ├── main.py                 ← FastAPI app + router registration
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── AlertPanel.jsx      ← alert submission form + example quick-loads
│       │   ├── TriageResult.jsx    ← severity badge, confidence meter, suggested fix
│       │   ├── ChatWidget.jsx     ← Floating chat + optional voice input
│       │   ├── VoiceButton.jsx    ← Microphone (requires VOICE_VOICE_ENABLED=true)
│       │   └── Sidebar.jsx        ← navigation + backend health indicator
│       └── App.jsx
├── infrastructure/
│   ├── k8s/
│   │   └── chromadb.yaml       ← Deployment + Service + PVC (Helm-annotated)
│   ├── helm/                   ← Phase 4
│   ├── terraform/              ← Phase 4
│   └── argocd/                 ← Phase 4
├── monitoring/
│   ├── prometheus/             ← Phase 3
│   └── grafana/                ← Phase 3
├── Dockerfile                  ← production image (non-root, healthcheck, 2 workers)
├── Makefile                    ← all dev commands
└── .env.example
```

---

## Quick Start

### Prerequisites

- macOS Apple Silicon (M1/M2/M3/M4)
- Python 3.11 (`brew install python@3.11`)
- Node.js 20+ (`brew install node`)
- Minikube (`brew install minikube`)
- Ollama (`brew install ollama`)

### One-time setup

```bash
git clone <repo-url> && cd sre-ai-copilot

# 1. Install Python deps (3.11 required — 3.14 not yet supported by PyO3)
make setup

# 2. Pull LLM models (~4.4 GB total)
make ollama-setup

# 3. Start Ollama (Metal GPU, keep this terminal open)
ollama serve
```

### Daily dev

```bash
# Terminal 1 — Infrastructure (ChromaDB in Minikube)
minikube start
make start-infra          # Ollama + ChromaDB on :8000

# Terminal 2 — Observability + demo stack (once per Minikube session)
make deploy-all           # Prometheus, Loki, Promtail, OTel, synthetic apps, Kafka
make dev-up               # after sleep/restart — refresh :19090/:13100 port-forwards
make kafka-port-forward   # Kafka :9092 (separate terminal)

# Terminal 3 — Backend (hot reload)
source venv/bin/activate
make start-backend        # FastAPI on :8080

# Terminal 4 — Ingest + Frontend
make ingest
make ingest-profile      # resume-only RAG for /resume recruiter Q&A (ChromaDB sre_candidate_profile)
make start-frontend       # React on http://localhost:5173
```

Set observability URLs in `.env` (see `.env.example`):

```
PROMETHEUS_URL=http://localhost:19090
LOKI_URL=http://localhost:13100
KAFKA_ENABLED=true
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
```

Verify the Observe page data path:

```bash
make observability-status
make status
```

### Verify everything is working

```bash
make status
```

Expected:
```
=== Backend (localhost:8080) ===
{"status": "healthy", "ollama_model": "mistral", "environment": "development"}
=== ChromaDB (localhost:8000) ===
 healthy
=== ChromaDB collections ===
{"status": "connected", "collections": {"incidents": 24, "runbooks": 31, "architecture": 8}}
=== Ollama (localhost:11434) ===
  models: ['mistral:latest', 'nomic-embed-text:latest']
```

### Test alert triage

```bash
curl -X POST http://localhost:8080/api/v1/triage \
  -H "Content-Type: application/json" \
  -d '{
    "name": "KubePodCrashLooping",
    "description": "ping-identity-auth pod restarting with OOMKilled exit code",
    "labels": {"namespace": "iam", "severity": "critical", "app": "ping-identity-auth"},
    "value": 8,
    "environment": "production"
  }' | python3 -m json.tool
```

---

## LLM Routing

Problem complexity is scored automatically from alert signals — no manual configuration:

```python
# Signals that increase complexity score
rag_hit_count == 0          # Novel problem, no historical precedent  (+4)
severity == "critical"      # AlertManager critical label             (+3)
risk keywords present       # "breach", "data loss", "unknown", etc.  (+2)
environment == "production" # Higher stakes                           (+1)
```

| Score | Complexity | LLM Tier | Model | Cost/month* |
|---|---|---|---|---|
| 0-1 | LOW | LOCAL | Mistral 7B | $0 |
| 2-3 | MEDIUM | STANDARD | Gemini 1.5 Flash | ~$0.11 |
| 4-6 | HIGH | ADVANCED | Claude Haiku 4.5 | ~$2.40 |
| 7+ | CRITICAL | PREMIUM | Claude Sonnet 4.6 | pay-per-use |

\* based on 1,000 escalated alerts/month

**Security:** External LLMs are disabled by default (`allow_external_llm=false`). When enabled, all payloads are sanitized (hostnames, IPs, credentials redacted) and every call is audit-logged.

---

## Adding a New Agent (Phase 2+)

```python
# 1. backend/agents/your_agent.py
class YourAgent(BaseAgent):
    def run(self, payload: dict) -> dict:
        docs = self._retrieve(query, collection="runbooks")
        llm, safe_payload, tier, complexity = self._route_llm(payload, len(docs))
        # ... domain logic
        return result

# 2. backend/routers/your_router.py
router = APIRouter(prefix="/api/v1", tags=["your-feature"])
_agent = YourAgent()

@router.post("/your-endpoint")
def your_endpoint(payload: YourPayload):
    result = _agent.execute(payload.model_dump())
    result.pop("_meta", None)
    return result

# 3. backend/main.py — one line
app.include_router(your_router.router)
```

## Adding a New Knowledge Domain

```bash
# 1. Create directory with markdown files
mkdir backend/knowledge/slos/
echo "# SLO: Token Service\nTarget: p99 < 200ms..." > backend/knowledge/slos/token_service.md

# 2. Register in config.py
knowledge_collections = {
    "incidents": "sre_incidents",
    "runbooks":  "sre_runbooks",
    "slos":      "sre_slos",      # ← add this line
}

# 3. Ingest
make ingest
```

### Recruiter profile RAG (`/resume`)

The recruiter Ask panel uses a **separate** ChromaDB collection (`sre_candidate_profile`) indexed from `backend/routers/resume_content.py` — not runbooks or architecture docs.

```bash
make ingest-profile
# or via API (backend running):
curl -X POST http://localhost:8080/api/v1/ingest/profile/sync

# verify chunk count:
curl -s http://localhost:8080/api/v1/knowledge/status | python -m json.tool
```

On backend startup, profile ingest runs automatically if the collection is empty (requires Ollama + `nomic-embed-text`).

### Railway: persistent resume analytics

Resume view counts use SQLite. Without a volume, data is lost on redeploy.

1. In Railway → your service → **Volumes** → add mount path `/data` (1 GB is enough).
2. Set environment variable `DATA_DIR=/data` (database file: `/data/recruiter.db`).
3. Set `ADMIN_TOKEN` and open `/resume?admin` with that token.

The frontend sets a 90-day `sreai_visitor` cookie for per-device unique counts; `session_id` in sessionStorage still links tab sessions.

---

## Roadmap

| Phase | Status | Key deliverables |
|---|---|---|
| **Phase 1 — Local prototype** | ✅ Complete | Ollama + Mistral, RAG pipeline, ChromaDB, FastAPI, React, Minikube, LLM routing |
| **Phase 2 — Intelligence** | ✅ Complete | ReAct agents, LangGraph executor, supervisor, conversation memory, runbook executor, RCA generator, knowledge chat, incident analysis, voice plugin |
| **Phase 3 — Auto-Learning** | 🔧 In progress | LearningAgent (`resolved_incidents` collection, resolve endpoint, auto-runbook promotion) |
| **Phase 4 — Production** | ⬜ Planned | EKS + Terraform, Helm charts, ArgoCD GitOps, GitHub Actions CI/CD, Karpenter |

---

## Ports

| Service | Port | Runtime |
|---|---|---|
| Ollama | 11434 | Native macOS (Metal GPU) |
| ChromaDB | 8000 | Minikube (port-forwarded) |
| FastAPI backend | 8080 | Native Python 3.11 venv |
| React frontend | 5173 | Native Node (Vite) |
