# SRE AI Copilot — Architecture & Design Reference

> **Audience:** SRE engineers, platform team, security reviewers.  
> **Last updated:** 2026-05-21  
> **Stack:** Python 3.12 · FastAPI · LangChain · **LangGraph 0.2** · ChromaDB · Ollama · React 18 · Minikube

---

## Table of Contents

1. [What We're Building](#1-what-were-building)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Multi-Agent System](#3-multi-agent-system)
4. [LangGraph Implementation](#4-langgraph-implementation)
5. [Agent Reference](#5-agent-reference)
6. [RAG Pipeline](#6-rag-pipeline)
7. [LLM Routing](#7-llm-routing)
8. [Alert-to-Resolution Flow](#8-alert-to-resolution-flow)
9. [Auto-Learning Loop (Phase 3)](#9-auto-learning-loop-phase-3)
10. [Frontend Architecture](#10-frontend-architecture)
11. [Infrastructure & Observability](#11-infrastructure--observability)
12. [Security Model](#12-security-model)
13. [API Reference](#13-api-reference)
14. [Directory Layout](#14-directory-layout)
15. [Phase Roadmap](#15-phase-roadmap)

---

## 1. What We're Building

SRE AI Copilot is an **on-premise, LLM-powered incident response platform** that sits between your alerting stack and your on-call engineers. It does three things that today require human judgment:

| Problem | What SRE AI does |
|---------|-----------------|
| Alert fatigue — 200 alerts, which one matters? | Triages severity (P1–P3) with confidence score using RAG over past incidents |
| "I've seen this before but can't remember the fix" | Retrieves exact runbook steps + commands from a vector knowledge base |
| Same incidents recurring every week | Learns from every resolved incident and routes future occurrences straight to the known fix |

**Everything runs locally by default.** No alert data, hostnames, or credentials leave the machine unless you explicitly configure an external LLM tier.

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        KUBERNETES CLUSTER (Minikube)                │
│                                                                     │
│  ┌──────────────┐    ┌─────────────────┐    ┌──────────────────┐   │
│  │  Prometheus  │───▶│  AlertManager   │───▶│  Webhook Route   │   │
│  │  (scrapes    │    │  (routes based  │    │  → SRE AI :8080  │   │
│  │   metrics)   │    │   on severity)  │    └──────────────────┘   │
│  └──────────────┘    └─────────────────┘                           │
│         ▲                                                           │
│  ┌──────┴──────────────────────────────────────────────────────┐   │
│  │  Java OOM Demo App (demo namespace)                         │   │
│  │  Leaks 2MB/500ms → OOMKilled (exit 137) → alert fires      │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                               │ webhook POST /api/v1/webhook/alertmanager
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     SRE AI BACKEND  (FastAPI :8080)                 │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    AGENT ORCHESTRATOR                        │   │
│  │                                                             │   │
│  │  Webhook ──▶ TriageAgent ──▶ [Phase 2] ExecutorAgent       │   │
│  │  Chat    ──▶ ChatAgent                    │                │   │
│  │  Runbook ──▶ RunbookAgent                 ▼                │   │
│  │  RCA     ──▶ RCAAgent         [Phase 2] LearningAgent      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────┐  ┌───────────────┐  ┌────────────────────┐  │
│  │   RAG Pipeline   │  │  LLM Router   │  │  Dedup Store       │  │
│  │  ChromaDB        │  │  LOCAL →      │  │  dict[(name, ns)]  │  │
│  │  nomic-embed     │  │  STANDARD →   │  │  RecentTriage      │  │
│  │  3 collections   │  │  ADVANCED →   │  │  fire_count        │  │
│  │  runbooks        │  │  PREMIUM      │  └────────────────────┘  │
│  │  incidents       │  └───────────────┘                          │
│  │  architecture    │                                             │
│  └──────────────────┘                                             │
│                                                                     │
│  ┌────────────────────────┐   ┌──────────────────────────────┐    │
│  │  Ollama (local LLM)    │   │  Session Store (in-memory)   │    │
│  │  llama3.1:8b           │   │  chat history per session_id │    │
│  │  nomic-embed-text      │   │  max 10 exchanges / session  │    │
│  └────────────────────────┘   └──────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   REACT FRONTEND  (Vite :5173 / proxied)            │
│                                                                     │
│  Sidebar ──▶ Alert Triage page   (manual alert submission)          │
│          ──▶ Live Incidents page  (auto-triaged alerts, polls 15s)  │
│          ──▶ Runbook Executor     (step-by-step guided remediation) │
│          ──▶ Auto RCA             (root cause analysis)             │
│          ──▶ [Soon] Anomaly Watch                                   │
│                                                                     │
│  ChatWidget (floating, always visible) ──▶ /api/v1/chat            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Multi-Agent System

> **Phase 2 shipped:** ExecutorAgent and SupervisorAgent are now implemented as LangGraph StateGraphs. See §4 for the full LangGraph design.

Yes — this is a **multi-agent system**. Each agent is a specialised autonomous unit with its own prompt, tools, and responsibility. They share a common base class but never call each other directly; the orchestration happens at the router/webhook layer.

### Agent Map

```
                        ┌──────────────────────────────────┐
                        │         BaseAgent (ABC)           │
                        │  _route_llm()   _retrieve()       │
                        │  execute()      _fallback_response│
                        └──────────────┬───────────────────┘
                                       │ inherits
          ┌────────────────────────────┼────────────────────────────┐
          │                            │                            │
    ┌─────▼──────┐             ┌──────▼──────┐             ┌──────▼──────┐
    │TriageAgent │             │  ChatAgent  │             │RunbookAgent │
    │            │             │             │             │             │
    │Input:      │             │Input:       │             │Input:       │
    │  alert     │             │  question   │             │  issue_type │
    │  payload   │             │  session_id │             │  namespace  │
    │            │             │             │             │  service    │
    │RAG:        │             │RAG:         │             │             │
    │  incidents │             │  runbooks   │             │RAG:         │
    │  (k=3)     │             │  arch (k=2) │             │  runbooks   │
    │            │             │             │             │  (k=5)      │
    │Output:     │             │Output:      │             │             │
    │  severity  │             │  answer     │             │Output:      │
    │  reasoning │             │  sources    │             │  steps[]    │
    │  fix steps │             │  llm_tier   │             │  risk_level │
    │  escalate  │             │             │             │  commands   │
    └─────┬──────┘             └─────────────┘             └─────────────┘
          │
          │  [Phase 2 — coming next]
          ▼
    ┌─────────────┐             ┌──────────────┐
    │ExecutorAgent│             │LearningAgent │
    │             │────────────▶│              │
    │ReAct loop:  │  on success │Writes back   │
    │  Reason     │             │to ChromaDB   │
    │  Act        │             │"resolved_    │
    │  Observe    │             │ incidents"   │
    │  Reason...  │             │collection    │
    │             │             │              │
    │Tools:       │             │Also updates  │
    │  kubectl_   │             │dedup store   │
    │  get/desc/  │             │with outcome  │
    │  restart/   │             │              │
    │  patch/     │             └──────────────┘
    │  scale      │
    │             │             ┌──────────────┐
    │Guardrails:  │             │  RCAAgent    │
    │  read-auto  │             │              │
    │  write-gate │             │Input:        │
    │  no delete  │             │  incident_id │
    │  no drain   │             │  symptoms    │
    └─────────────┘             │  timeline    │
                                │              │
                                │Output:       │
                                │  root_cause  │
                                │  timeline    │
                                │  prevention  │
                                └──────────────┘
```

---

## 4. LangGraph Implementation

We use **LangGraph 0.2** as the execution backbone for both the ExecutorAgent and the SupervisorAgent. LangGraph turns the agents from plain Python functions into proper state machines with checkpointing, parallel dispatch, and human-in-the-loop interrupts.

### Why LangGraph over a plain while-loop?

| Concern | Plain while-loop (Phase 1) | LangGraph StateGraph (Phase 2) |
|---------|---------------------------|-------------------------------|
| **Parallel tool dispatch** | Sequential — get_pods, then get_logs, then top_pods | All 3 fire simultaneously via `Send` API — 3× faster gather |
| **State persistence** | Python dict in RAM — lost on restart | `MemorySaver` checkpoints at every node — survives restarts |
| **Approval gate** | Manual `approved=False` flag + loop check | `interrupt_before=["execute_write"]` — graph literally pauses at a node boundary |
| **Debuggability** | Opaque — need to add print statements | Every node transition is a named edge — visual graph, traceable |
| **Cross-call resume** | Requires custom state store + lookup | `graph.invoke(None, config={"thread_id": id})` — LangGraph rehydrates from checkpoint |

---

### ExecutorAgent Graph

```
START
  │
  ▼  route_parallel_gather() → returns [Send("gather_pods"), Send("gather_logs"), Send("gather_metrics")]
  │
  ├──▶ gather_pods     ─────┐
  ├──▶ gather_logs     ─────┼──▶  reason  ◀──────────────────────────┐
  └──▶ gather_metrics  ─────┘       │                                 │
  (all 3 run concurrently)          │  route_after_reason()           │
                                    ├──▶ execute_read  ───────────────┘
                                    ├──▶ execute_write ───────────────┘  ← interrupt_before here
                                    └──▶ END
```

**Key LangGraph concepts used:**

```python
# 1. Parallel dispatch — Send API
def route_parallel_gather(state):
    return [
        Send("gather_pods",    state),   # fires simultaneously
        Send("gather_logs",    state),   # fires simultaneously
        Send("gather_metrics", state),   # fires simultaneously
    ]
builder.add_conditional_edges("__start__", route_parallel_gather,
                               ["gather_pods", "gather_logs", "gather_metrics"])

# 2. Append-only scratchpad — Annotated reducer
class ExecutorState(TypedDict):
    scratchpad: Annotated[list[dict], operator.add]
# Each node returns {"scratchpad": [new_step]}
# LangGraph APPENDS it — parallel nodes don't overwrite each other

# 3. MemorySaver — cross-API-call persistence
checkpointer = MemorySaver()
graph = builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["execute_write"],   # pause before ANY write tool
)

# 4. Start execution
graph.invoke(initial_state, config={"configurable": {"thread_id": execution_id}})

# 5. Resume after human approval (input=None means "continue from checkpoint")
graph.invoke(None, config={"configurable": {"thread_id": execution_id}})

# 6. Inspect state without resuming
snapshot = graph.get_state(config)
snapshot.values        # full current state
snapshot.next          # which nodes are next (["execute_write"] if paused)
```

---

### SupervisorAgent Graph

```
START
  │
  ▼
classify   ← LLM classifies intent (triage|chat|runbook|rca|execute)
  │
  │  route_to_specialist()
  ├──▶ triage_node   ──┐
  ├──▶ chat_node     ──┤
  ├──▶ runbook_node  ──┼──▶ merge ──▶ END
  ├──▶ rca_node      ──┤
  └──▶ execute_node  ──┘
```

The classify node uses `temperature=0.0` for deterministic routing. Each specialist node calls the underlying agent and writes its result to its own state key. The merge node normalizes into a single response.

**Future parallel pattern** — fire triage + chat simultaneously for complex alerts:
```python
def route_parallel(state):
    return [
        Send("triage_node", state),   # classify severity
        Send("chat_node",   state),   # pre-fetch runbooks while triaging
    ]
# Both results available to merge node — no sequential wait
```

---

### Why separate agents?

| Principle | How we apply it |
|-----------|----------------|
| **Single responsibility** | Each agent does one thing. TriageAgent classifies. ChatAgent answers questions. ExecutorAgent acts. |
| **Independent LLM routing** | Each agent scores complexity independently — a chat question and a P1 triage get different LLM tiers |
| **Isolated failure** | If RCAAgent fails, triage still works. The `execute()` wrapper catches and returns safe defaults |
| **Testable in isolation** | Unit tests mock `_route_llm` and `_retrieve` — no Ollama needed in CI |
| **Composable** | ExecutorAgent will call TriageAgent's output as its input payload, enabling agent chaining |

---

## 4. Agent Reference

### TriageAgent

**Purpose:** Classify incoming alert severity, suggest exact remediation.

**Trigger:** `POST /api/v1/triage` (manual) or AlertManager webhook (background task)

**Flow:**
1. RAG retrieval from `incidents` collection (k=3) — finds similar past incidents
2. Complexity scoring → LLM tier selection
3. Prompt fills: severity matrix + similar incidents + alert payload
4. LLM returns structured JSON (severity, reasoning, suggested_fix, escalate, confidence)
5. Result stored in dedup store keyed by `(alert_name, namespace)`

**Deduplication:** If same `(alert_name, namespace)` fires again, `fire_count` increments instead of creating a new record. This prevents alert storms from flooding the UI.

---

### ChatAgent

**Purpose:** On-call Q&A assistant. Answers questions about runbooks, architecture, past incidents.

**Trigger:** `POST /api/v1/chat` from the floating ChatWidget

**Flow:**
1. RAG retrieval from `runbooks` (k=4) + `architecture` (k=2) collections
2. Conversation history fetched from `InMemorySessionStore` (max 10 exchanges)
3. Structured response format: **What's happening → Immediate actions → Why → Escalate if**
4. When context is partial: fills with standard K8s/SRE practice, labels as `(standard practice)`
5. History updated, sources returned alongside answer

**Session management:** Each browser tab gets a random `SESSION_ID`. `/api/v1/chat/{session_id}` (DELETE) clears it.

---

### RunbookAgent

**Purpose:** Execute a runbook interactively — break it into ordered steps with exact commands.

**Trigger:** `POST /api/v1/runbook`

**Flow:**
1. RAG retrieval from `runbooks` collection (k=5)
2. LLM generates ordered steps with commands, expected outputs, and rollback instructions
3. Returns `steps[]`, `risk_level`, `estimated_time`, `rollback_steps[]`

---

### RCAAgent

**Purpose:** Root cause analysis for post-incident review.

**Trigger:** `POST /api/v1/rca`

**Flow:**
1. RAG retrieval from `incidents` + `architecture` collections
2. LLM reasons over timeline, symptoms, and contributing factors
3. Returns `root_cause`, `contributing_factors[]`, `timeline[]`, `prevention[]`, `action_items[]`

---

### ExecutorAgent *(Phase 2 — implemented)*

**Purpose:** Autonomously execute the fix suggested by TriageAgent. ReAct loop with kubectl tools.

**Implementation:** `backend/agents/executor_agent.py` — LangGraph StateGraph with parallel gather, MemorySaver checkpointing, and `interrupt_before=["execute_write"]` approval gates.

**Allowed tools (read — automatic, write — approval gate):**

| Tool | Type | Auto? |
|------|------|-------|
| `kubectl_get(resource, namespace)` | read | yes |
| `kubectl_describe(resource, namespace)` | read | yes |
| `kubectl_logs(pod, namespace, tail)` | read | yes |
| `kubectl_top(namespace)` | read | yes |
| `kubectl_rollout_restart(deployment, namespace)` | write | **approval** |
| `kubectl_patch_resources(deployment, namespace, limits)` | write | **approval** |
| `kubectl_scale(deployment, namespace, replicas)` | write | **approval** |
| `kubectl_delete_pod(pod, namespace)` | write | **approval** |

**Never allowed:** `kubectl delete deployment`, `kubectl drain`, `kubectl cordon`, any cluster-wide operations.

**Confidence gate:** Only triggers auto-execution if:
- RAG similarity score > 0.85 on a prior *successful* resolution
- Same `(alert_name, namespace)` has been seen ≥ 2 times before
- Severity is P2 or P3 (P1 always requires human approval regardless)

---

### LearningAgent *(Phase 3 — implemented)*

**Purpose:** Write successful resolutions back into the knowledge base so the next occurrence is handled faster.

**Implementation:** `backend/agents/learning_agent.py` — ingests into `sre_resolved_incidents` ChromaDB collection on ExecutorAgent `resolved` status or via `POST /api/v1/incidents/{id}/resolve`.

**Trigger:** Called automatically when ExecutorAgent completes with `status=resolved`, or manually via the resolve endpoint.

**What it stores:**
```json
{
  "alert_name": "JavaPodOOMKilled",
  "namespace": "demo",
  "resolution_steps": ["kubectl describe pod ...", "kubectl patch ..."],
  "outcome": "alert_cleared",
  "time_to_resolve_seconds": 47,
  "fire_count_at_resolution": 3,
  "resolved_at": "2026-05-21T10:32:00Z"
}
```

**Storage:** Ingests into a new ChromaDB collection `resolved_incidents` (separate from `incidents` which holds historical runbook content). This collection gets higher RAG weight for the ExecutorAgent.

**Feedback loop:** After N successful auto-resolutions of the same alert type, the system promotes the resolution to a full runbook entry in the `runbooks` collection. This is the "auto-learning" — the bot literally writes its own runbooks.

---

## 5. RAG Pipeline

```
Knowledge files (Markdown)
        │
        ▼
  Ingestor (rag/ingestor.py)
  ├── RecursiveCharacterTextSplitter
  │   chunk_size=800, overlap=80
  ├── OllamaEmbeddings (nomic-embed-text)
  │   768-dimensional vectors, runs 100% local
  └── ChromaDB (persistent, .chromadb-data/)
      ├── collection: "runbooks"     (69 chunks)  ← step-by-step remediation
      ├── collection: "incidents"    (29 chunks)  ← historical incident reports
      ├── collection: "architecture" (4 chunks)   ← system topology docs
      └── [Phase 2] collection: "resolved_incidents"  ← auto-learned fixes
              │
              ▼
  Retriever (rag/retriever.py)
  ├── retrieve_with_score(query, collection, k)
  ├── Returns [(Document, distance_score), ...]
  └── distance → similarity: sim = max(0, 1 - distance)
```

**Why nomic-embed-text?** 768-dim open-source embedding model that runs via Ollama. No API calls, no data leaving the machine. Comparable quality to OpenAI `text-embedding-3-small` for technical runbook content.

---

## 6. LLM Routing

Every agent independently scores complexity and routes to the appropriate LLM tier. This means a routine chat question uses the local Llama model for free, while a novel P1 security incident can escalate to Claude Sonnet.

```
Alert/Question arrives
        │
        ▼
score_complexity(payload, rag_hit_count)
        │
        ├── RAG hits = 0          → +4 points  (novel problem, no precedent)
        ├── RAG hits < threshold  → +2 points
        ├── label: severity=critical → +3 points
        ├── label: severity=warning  → +1 point
        ├── risk keywords in text    → +2 points
        └── environment=production   → +1 point
        │
        ▼
  Score → Complexity → Tier → LLM

  0-1  → LOW      → LOCAL    → llama3.1:8b (Ollama, $0)
  2-3  → MEDIUM   → STANDARD → gemini-1.5-flash ($0.11/mo est.)
  4-6  → HIGH     → ADVANCED → claude-haiku-4-5  ($2.40/mo est.)
  7+   → CRITICAL → PREMIUM  → claude-sonnet-4-6 (pay-per-use)
```

**Data safety:** All non-LOCAL tiers pass the payload through `sanitizer.py` which redacts:
- IP addresses and hostnames
- Kubernetes secret values
- Bearer tokens and API keys
- Internal namespace patterns (`*.svc.cluster.local`)

Every external LLM call is audit-logged via `audit_logger` (route to SIEM/CloudWatch in production).

**Kill switch:** `ALLOW_EXTERNAL_LLM=false` (default) blocks all non-LOCAL tiers. Everything falls back to Ollama silently.

---

## 7. Alert-to-Resolution Flow

### Current (Phase 1) — Triage + Suggest

```
Java pod OOMKills (exit 137)
        │
        ▼
Prometheus scrapes kube_pod_container_status_last_terminated_reason
        │  (15s scrape interval)
        ▼
PrometheusRule fires: JavaPodOOMKilled
        │
        ▼
AlertManager routes to SRE AI webhook
POST http://host.minikube.internal:8080/api/v1/webhook/alertmanager
        │
        ▼
FastAPI BackgroundTask → TriageAgent.execute()
  ├── RAG: finds java_oom_resolution.md, pod_crashloop.md
  ├── LLM: scores complexity → routes to llama3.1:8b (LOCAL tier)
  ├── Returns: severity=P2, reasoning, suggested_fix commands
  └── Stores in dedup dict: key=(JavaPodOOMKilled, demo)
        │
        ▼
UI polls GET /api/v1/webhook/alertmanager/recent every 15s
        │
        ▼
Live Incidents page shows:
  ┌──────────────────────────────────────────────────────┐
  │ ● P2  JavaPodOOMKilled              demo  ×3         │
  │ Increase memory limit or add JVM heap flags           │
  │ $ kubectl patch deployment oom-demo -n demo ...       │
  └──────────────────────────────────────────────────────┘
```

### Planned (Phase 2) — Execute + Learn

```
[Same flow up to TriageAgent stores result]
        │
        ▼
Check: fire_count >= 2 AND confidence > 0.85 AND severity != P1?
        │
        ├── NO  → Show "Execute Fix" button in UI (semi-auto mode)
        │         User clicks → ExecutorAgent runs with approval gates
        │
        └── YES → ExecutorAgent auto-executes (non-destructive actions only)
                    │
                    ▼
              ReAct loop:
              1. kubectl describe pod oom-demo-xxx -n demo
              2. kubectl patch deployment oom-demo -n demo \
                   -p '{"spec":{"template":{"spec":{"containers":[
                     {"name":"oom-demo","resources":{"limits":{"memory":"256Mi"}}}
                   ]}}}}'
              3. kubectl rollout status deployment/oom-demo -n demo
              4. Check: alert cleared? → YES
                    │
                    ▼
              LearningAgent.ingest(resolution_path)
              → Writes to ChromaDB "resolved_incidents"
              → Next occurrence: retrieved immediately, confidence=0.95
              → After 3 successes: auto-promoted to runbook
```

---

## 8. Auto-Learning Loop (Phase 2)

This is what makes the system genuinely self-improving:

```
Incident #1 (fire_count=1)
  └── Triage only. Human executes fix manually.
  
Incident #2 (fire_count=2)
  └── Triage + "Execute Fix" button. Human approves each step.
      On success → LearningAgent writes resolution to ChromaDB.

Incident #3 (fire_count=3, resolution in RAG, similarity=0.95)
  └── Triage + ExecutorAgent auto-executes read-only steps.
      Pauses for write approval. Human clicks "Approve" once.
      On success → LearningAgent updates resolution confidence.

Incident #5+ (fire_count≥5, similarity=0.98)
  └── Full auto-remediation for P2/P3. P1 always gates.
      After 3 consecutive auto-successes → promoted to runbook.
      Next occurrence resolves in ~30s vs ~15min manual.
```

**The feedback mechanism:**

```
ChromaDB "resolved_incidents" collection
        │
        ├── Each entry: alert_name, namespace, steps, outcome, duration
        │
        ├── TriageAgent RAG picks these up automatically
        │   (same retriever, higher collection weight)
        │
        ├── ExecutorAgent uses similarity score to decide confidence
        │
        └── After threshold successes → RunbookIngestor writes
            new markdown file to knowledge/runbooks/auto/
            and re-ingests into "runbooks" collection
```

---

## 9. Frontend Architecture

```
frontend/src/
├── App.jsx              ← Route controller (activeView state)
├── components/
│   ├── Sidebar.jsx      ← Nav + live incident badge (polls /recent 15s)
│   ├── AlertPanel.jsx   ← Manual alert triage form + result
│   ├── IncidentsPage.jsx  ← Live incidents dedicated page
│   ├── LiveIncidents.jsx  ← Incident cards with filters + fire count
│   ├── RunbookPanel.jsx   ← Runbook executor UI
│   ├── RCAPanel.jsx       ← RCA form + structured output
│   ├── TriageResult.jsx   ← Triage output card (severity chip, steps)
│   ├── ChatWidget.jsx     ← Floating chat (CLOSED/OPEN/MAX states)
│   └── ChatInterface.jsx  ← Full-page chat (legacy, superseded by widget)
```

### State Management

No Redux/Zustand — local `useState` per component. The only cross-component state is `activeView` in `App.jsx` passed down as props. This is intentional — the app is simple enough that global state would be overengineering.

### Chat Widget States

```
CLOSED: Just the floating button (bottom-right)
         └── Unread badge shows count of new messages received while closed

OPEN:   400×560px panel anchored bottom-right
         └── Full chat history, markdown rendering, code copy buttons

MAX:    Full-screen overlay (fixed inset-4)
         └── Same as OPEN but maximised for reading long runbook outputs
```

### Key Design Decisions

- **Floating ChatWidget** replaces the Knowledge Chat nav item — always available regardless of which page the engineer is on. During an incident you don't want to lose context by switching tabs.
- **Live Incidents as a separate page** — moved out of AlertPanel to avoid crowding. AlertPanel is now purely for manual triage submission.
- **15s polling** — no WebSocket because the backend is stateless and the polling interval matches Prometheus scrape intervals.
- **Namespace filter tabs** in LiveIncidents — filters by Kubernetes namespace so Citi's IAM team only sees `iam` alerts, CISO team sees `ciso` alerts.

---

## 10. Infrastructure & Observability

### Kubernetes Setup (Minikube)

```
Namespaces:
├── monitoring    ← kube-prometheus-stack (Prometheus, Grafana, AlertManager)
├── demo          ← Java OOM demo app (proves the alert→triage loop)
└── default       ← SRE AI backend (or run on host via host.minikube.internal)

Key manifests (infrastructure/k8s/):
├── oom-demo.yaml              ← Java deployment, 96Mi memory limit
├── oom-prometheusrule.yaml    ← PrometheusRule: JavaPodOOMKilled
├── sre-ai-external-service.yaml  ← Headless Service + Endpoints → host machine
├── grafana-dashboard-configmap.yaml  ← Auto-discovered Grafana dashboard
└── chromadb.yaml              ← ChromaDB in-cluster (optional)
```

### AlertManager Webhook Config

AlertManager is configured by patching the `alertmanager-kube-prometheus-stack-alertmanager` Secret directly (not via AlertmanagerConfig CRD, which auto-injects namespace matchers and would miss cross-namespace alerts):

```yaml
route:
  receiver: sre-ai-webhook
  group_by: [alertname, namespace]
  group_wait: 10s
  group_interval: 5m
receivers:
  - name: sre-ai-webhook
    webhook_configs:
      - url: http://host.minikube.internal:8080/api/v1/webhook/alertmanager
        send_resolved: false
```

### Grafana Dashboard (11 panels)

| Panel | Metric | What it tells you |
|-------|--------|-------------------|
| HTTP Request Rate | `sre_ai_http_requests_total` | Overall API traffic |
| p95 Latency | `sre_ai_request_duration_seconds` | Slow agent runs |
| Triage Volume | `sre_ai_triage_total` | Alert ingestion rate |
| Agent Duration | `sre_ai_agent_duration_seconds` | Per-agent perf breakdown |
| LLM Tier Split | `sre_ai_llm_tier_total` | Cost monitoring (local vs external) |
| RAG Hit Rate | `sre_ai_rag_hits_total` | Knowledge base coverage |
| Escalation Rate | `sre_ai_escalations_total` | P1 frequency |
| OOM Restarts | `kube_pod_container_status_restarts_total` | Demo app health |
| Pod CPU | `container_cpu_usage_seconds_total` | Resource pressure |
| Pod Memory | `container_memory_usage_bytes` | Memory trends |
| Alert Webhook Rate | `sre_ai_webhook_received_total` | AlertManager connectivity |

---

## 11. Security Model

### Data Boundary

```
┌────────────────────────────────────────────────────────┐
│  LOCAL BOUNDARY (never leaves machine)                  │
│                                                         │
│  • Alert payloads (names, labels, descriptions)         │
│  • Kubernetes metadata (namespaces, pod names)          │
│  • RAG retrieval queries                                │
│  • Runbook content                                      │
│  • LLM inference (llama3.1:8b via Ollama)              │
│  • Embeddings (nomic-embed-text via Ollama)            │
└────────────────────────────────────────────────────────┘
         │ Only if ALLOW_EXTERNAL_LLM=true AND complexity >= MEDIUM
         ▼
┌────────────────────────────────────────────────────────┐
│  SANITIZED PAYLOAD (external LLM tiers)                 │
│                                                         │
│  sanitizer.py redacts before any external call:         │
│  • IP addresses → [REDACTED_IP]                         │
│  • Hostnames → [REDACTED_HOST]                          │
│  • *.svc.cluster.local → [REDACTED_K8S_SVC]            │
│  • Bearer/API tokens → [REDACTED_TOKEN]                 │
│  • Kubernetes secret values → [REDACTED_SECRET]         │
│                                                         │
│  audit_log() writes to llm.audit logger for every call  │
│  (route to CloudWatch/SIEM in production)               │
└────────────────────────────────────────────────────────┘
```

### RBAC for ExecutorAgent (Phase 2)

The ExecutorAgent will use a dedicated ServiceAccount with minimal RBAC:

```yaml
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/log", "services", "endpoints"]
    verbs: ["get", "list", "describe"]          # always allowed
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets"]
    verbs: ["get", "list", "patch"]              # patch for resource limit updates
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["update"]                            # for rollout restart
# Explicitly NOT granted: delete, create on nodes, PV, secrets, RBAC resources
```

### Secrets

- `.env` is gitignored — never committed
- `ALLOW_EXTERNAL_LLM=false` is the default — external LLM requires explicit opt-in
- AlertManager webhook secret patched manually — not stored in source control

---

## 13. API Reference

| Method | Path | Agent | Description |
|--------|------|-------|-------------|
| `GET` | `/health` | — | Backend + Ollama health check |
| **`POST`** | **`/api/v1/ask`** | **SupervisorAgent** | **Single entry point — classifies + routes to specialist** |
| `POST` | `/api/v1/triage` | TriageAgent | Direct: manual alert triage |
| `POST` | `/api/v1/chat` | ChatAgent | Direct: on-call assistant Q&A |
| `DELETE` | `/api/v1/chat/{session_id}` | ChatAgent | Clear chat session |
| `POST` | `/api/v1/runbook/execute` | RunbookAgent | Direct: step-by-step runbook |
| `POST` | `/api/v1/rca` | RCAAgent | Direct: root cause analysis |
| `POST` | `/api/v1/webhook/alertmanager` | TriageAgent | AlertManager webhook receiver |
| `GET` | `/api/v1/webhook/alertmanager/recent` | — | Recent auto-triaged alerts (polls every 15s) |
| `POST` | `/api/v1/ingest` | — | Re-ingest knowledge base |
| `GET` | `/metrics` | — | Prometheus metrics endpoint |
| `POST` | `/api/v1/incidents/{id}/execute` | ExecutorAgent | Start LangGraph ReAct loop (parallel gather → reason → act) |
| `POST` | `/api/v1/incidents/{id}/approve/{exec_id}` | ExecutorAgent | Resume after human approval (graph.invoke None) |
| `GET` | `/api/v1/incidents/{id}/execution/{exec_id}` | ExecutorAgent | Poll scratchpad + status (frontend polls every 2s) |
| `POST` | `/api/v1/incidents/{id}/resolve` | LearningAgent | Mark outcome + trigger auto-learning |
| `POST` | `/api/v1/voice/transcribe` | VoiceAgent | STT only — used by ChatWidget voice input |
| `POST` | `/api/v1/voice/synthesize` | VoiceAgent | TTS only |
| `GET` | `/api/v1/voice/health` | — | Voice module status |
| `POST` | `/api/v1/incident/analyze` | — | Streaming incident analysis from pasted telemetry |
| `GET` | `/api/v1/observability/services` | — | Live service list from synthetic stack |

### Supervisor vs Direct endpoints

The `/api/v1/ask` endpoint is the **recommended** entry point — it auto-classifies intent and routes. The direct endpoints (`/triage`, `/chat`, `/runbook`, `/rca`) remain available for cases where the caller already knows which agent to invoke (e.g., AlertManager webhook always goes directly to `/webhook/alertmanager`).

---

## 13. Directory Layout

```
sre-ai/
├── backend/
│   ├── agents/
│   │   ├── base.py          ← BaseAgent: LLM routing, RAG retrieval, timing
│   │   ├── triage_agent.py  ← Alert severity classification
│   │   ├── chat_agent.py    ← On-call Q&A with conversation history
│   │   ├── runbook_agent.py ← Step-by-step runbook execution
│   │   └── rca_agent.py     ← Root cause analysis
│   ├── llm/
│   │   ├── router.py        ← Complexity scoring + LLM tier selection
│   │   └── sanitizer.py     ← PII/hostname redaction for external LLMs
│   ├── rag/
│   │   ├── embeddings.py    ← nomic-embed-text via Ollama
│   │   ├── ingestor.py      ← Chunk + embed + store to ChromaDB
│   │   └── retriever.py     ← Scored similarity retrieval
│   ├── memory/
│   │   ├── session_store.py ← In-memory chat history (10 exchanges max)
│   │   └── redis_store.py   ← Redis-backed store (optional, production)
│   ├── routers/
│   │   ├── triage.py        ← POST /api/v1/triage
│   │   ├── chat.py          ← POST /api/v1/chat
│   │   ├── runbook.py       ← POST /api/v1/runbook
│   │   ├── rca.py           ← POST /api/v1/rca
│   │   ├── alertmanager.py  ← Webhook + /recent endpoint
│   │   ├── health.py        ← GET /health
│   │   └── _models.py       ← Pydantic request/response models
│   ├── integrations/
│   │   ├── metrics.py       ← Prometheus counters/histograms
│   │   └── slack.py         ← Slack notification client
│   ├── knowledge/
│   │   ├── runbooks/        ← Markdown runbooks (8 files)
│   │   ├── incidents/       ← Historical incident reports (5 files)
│   │   └── architecture/    ← System topology docs (1 file)
│   ├── config.py            ← Settings (Pydantic BaseSettings, reads .env)
│   ├── main.py              ← FastAPI app + router registration
│   └── voice/               ← Optional voice plugin (STT/TTS, disabled by default)
├── synthetic/               ← Demo observability stack (Prometheus, Loki, demo apps)
├── frontend/
│   └── src/
│       ├── App.jsx           ← Route controller
│       └── components/       ← 9 React components (see §9)
├── infrastructure/
│   ├── demo/                 ← Java OOM demo app + Dockerfile
│   └── k8s/                  ← Kubernetes manifests
├── tests/
│   ├── unit/                 ← Agent unit tests (mocked LLM + RAG)
│   ├── integration/          ← API integration tests
│   └── e2e/                  ← Full stack smoke tests
└── ARCHITECTURE.md           ← This file
```

---

## 15. Phase Roadmap

| Phase | Status | What's included |
|-------|--------|----------------|
| **Phase 1 — Foundation** | ✅ Complete | TriageAgent, ChatAgent, RunbookAgent, RCAAgent, RAG pipeline, LLM routing, AlertManager webhook, Live Incidents UI, Grafana dashboard, Java OOM demo, E2E tests |
| **Phase 2 — Multi-Agent + Autonomous Resolution** | ✅ Complete | **LangGraph ExecutorAgent** (parallel gather + ReAct + MemorySaver), **SupervisorAgent** (classify → route), `POST /api/v1/ask`, approval gate endpoints |
| **Phase 3 — Auto-Learning** | 🔧 In progress | LearningAgent, `resolved_incidents` collection, resolve endpoint, auto-runbook promotion |
| **Phase 4 — Anomaly Watch** | 🔲 Planned | Time-series anomaly detection on Prometheus metrics, proactive alerting before thresholds breach |

### What Phase 2 delivered

**LangGraph ExecutorAgent** (`backend/agents/executor_agent.py`):
- `StateGraph` with `TypedDict` state — every field typed, LangGraph-managed
- `Send` API parallel dispatch — `gather_pods`, `gather_logs`, `gather_metrics` fire simultaneously
- `Annotated[list, operator.add]` scratchpad — parallel nodes safely append without overwriting
- `MemorySaver` checkpointing — state survives restarts, persists across API calls
- `interrupt_before=["execute_write"]` — graph pauses for human approval before any kubectl write
- Resume with `graph.invoke(None, config)` — LangGraph rehydrates from checkpoint

**SupervisorAgent** (`backend/agents/supervisor_agent.py`):
- `StateGraph` with intent classification node (temperature=0, deterministic)
- 5 specialist nodes: triage, chat, runbook, rca, execute
- Conditional routing from classify → specialist via `route_to_specialist()`
- Merge node normalizes all agent outputs into a single response format
- `POST /api/v1/ask` — single entry point replaces frontend needing to know which endpoint to call

### Phase 3 implementation plan (Auto-Learning)

1. `backend/agents/learning_agent.py` — on successful execution, embed scratchpad → ChromaDB `resolved_incidents`
2. Confidence gate in ExecutorAgent: if RAG similarity > 0.85 on prior resolution → skip exploration, go straight to known fix
3. Auto-promotion: after 3 consecutive successes → write new markdown runbook to `knowledge/runbooks/auto/`
4. Parallel SupervisorAgent: for complex alerts, fire `triage_node` + `chat_node` simultaneously via `Send` — triage classifies while chat pre-fetches runbooks
5. `POST /api/v1/incidents/{id}/resolve` — human feedback endpoint to mark outcome + trigger learning
