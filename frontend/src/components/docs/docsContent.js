/** Enterprise documentation content — derived from codebase (ARCHITECTURE.md, main.py, routers). */

export const DOC_SECTIONS = [
  { id: "summary", label: "Executive Summary" },
  { id: "tech-stack", label: "Tech Stack" },
  { id: "architecture", label: "Architecture Overview" },
  { id: "data-flows", label: "Data Flows" },
  { id: "components", label: "Component Map" },
  { id: "integrations", label: "Integration Points" },
  { id: "security", label: "Security & Compliance" },
  { id: "deployment", label: "Deployment Topology" },
  { id: "api", label: "API Overview" },
];

export const TECH_STACK = [
  {
    layer: "Frontend",
    technology: "React 18 · Vite 6 · TailwindCSS",
    role: "Command Center, Observe, Incidents, Playbooks, AI Analysis, floating ChatWidget",
    status: "Shipped",
  },
  {
    layer: "Backend",
    technology: "FastAPI · Python 3.11+ · Uvicorn",
    role: "REST + SSE APIs, webhook receiver, Prometheus instrumentation",
    status: "Shipped",
  },
  {
    layer: "AI / Agents",
    technology: "LangGraph 0.2 · LangChain · Ollama (local LLM)",
    role: "Triage, Chat, Runbook, RCA, Executor (ReAct), Supervisor, Learning agents",
    status: "Shipped",
  },
  {
    layer: "RAG / Memory",
    technology: "ChromaDB · nomic-embed-text · Redis (optional)",
    role: "Runbook/incident retrieval; session, dedup, LangGraph checkpoints",
    status: "Shipped",
  },
  {
    layer: "Observability",
    technology: "Prometheus · Loki · Promtail · OTel Collector · Grafana",
    role: "Metrics, logs, synthetic demo stack, proactive anomaly watch",
    status: "Shipped",
  },
  {
    layer: "Event Bus",
    technology: "Kafka (aiokafka) + in-process SSE fan-out",
    role: "Durable incident/anomaly feeds; UI streams via EventSource",
    status: "Shipped (opt-in)",
  },
  {
    layer: "Storage",
    technology: "ChromaDB · SQLite checkpoints/audit · Redis · In-memory fallback",
    role: "Knowledge vectors, executor audit trail, session persistence",
    status: "Shipped",
  },
  {
    layer: "Voice (optional)",
    technology: "Whisper STT plugin",
    role: "Hands-free chat input when VOICE_VOICE_ENABLED=true",
    status: "Plugin",
  },
];

export const COMPONENT_MAP = [
  {
    path: "frontend/src/",
    purpose: "React SPA — enterprise dark UI with sre-* design tokens and Inter font",
    modules: ["App.jsx (view router)", "components/ (panels, layout, observability widgets)", "hooks/useSystemHealth.js"],
  },
  {
    path: "backend/main.py",
    purpose: "FastAPI entry — lifespan hooks for Kafka, anomaly watcher, Redis persistence",
    modules: ["Router registration", "CORS", "Prometheus /metrics"],
  },
  {
    path: "backend/agents/",
    purpose: "Specialist LLM agents with shared BaseAgent (routing, RAG, timing)",
    modules: ["triage_agent", "chat_agent", "runbook_agent", "rca_agent", "executor_agent (LangGraph)", "supervisor_agent", "learning_agent"],
  },
  {
    path: "backend/routers/",
    purpose: "HTTP API surface grouped by domain",
    modules: ["alertmanager", "events (SSE)", "observability", "incidents/execute", "audit", "chat", "triage", "runbook", "rca"],
  },
  {
    path: "backend/rag/",
    purpose: "Knowledge ingestion and similarity retrieval",
    modules: ["ingestor.py", "retriever.py", "embeddings.py (Ollama nomic-embed-text)"],
  },
  {
    path: "backend/llm/",
    purpose: "Complexity scoring, tiered LLM routing, payload sanitization",
    modules: ["router.py", "sanitizer.py"],
  },
  {
    path: "backend/memory/",
    purpose: "Session, dedup, checkpoints, audit — Redis with in-memory fallback",
    modules: ["persistence.py", "redis_store.py", "audit_store.py", "dedup_store.py", "checkpointer_factory.py"],
  },
  {
    path: "backend/integrations/",
    purpose: "External systems and real-time feeds",
    modules: ["kafka_bus.py", "live_events.py", "anomaly_watcher.py", "metrics.py", "slack.py"],
  },
  {
    path: "backend/knowledge/",
    purpose: "Markdown runbooks, incidents, architecture docs ingested into ChromaDB",
    modules: ["runbooks/", "incidents/", "architecture/", "resolved_incidents/"],
  },
  {
    path: "infrastructure/k8s/",
    purpose: "Minikube manifests — observability, Kafka, Redis, demo OOM app, ChromaDB",
    modules: ["observability/", "kafka/", "redis.yaml", "oom-demo.yaml", "grafana-dashboard-configmap.yaml"],
  },
  {
    path: "synthetic/",
    purpose: "Demo observability stack and synthetic Java/Python apps for Observe page",
    modules: ["observability/", "java-app/", "python-app/", "collector/"],
  },
  {
    path: "tests/",
    purpose: "Unit, integration, and E2E test suites",
    modules: ["unit/", "integration/", "e2e/"],
  },
];

export const INTEGRATIONS = [
  {
    name: "Prometheus",
    status: "Connected",
    description: "Scrapes demo + synthetic metrics; AlertManager fires webhooks to SRE AI",
    config: "PROMETHEUS_URL · port-forward :19090",
  },
  {
    name: "Loki + Promtail",
    status: "Connected",
    description: "Log aggregation for incident analysis and Observe page log panels",
    config: "LOKI_URL · port-forward :13100",
  },
  {
    name: "AlertManager",
    status: "Connected",
    description: "POST /api/v1/webhook/alertmanager → background TriageAgent",
    config: "infrastructure/k8s/alertmanager-sre-ai.yaml",
  },
  {
    name: "Kafka",
    status: "Optional",
    description: "Durable incident/anomaly topics; SSE always works in-process when broker down",
    config: "KAFKA_ENABLED · topics sre.incidents.triage, sre.observability.anomalies",
  },
  {
    name: "Redis",
    status: "Optional",
    description: "Session store, triage dedup, LangGraph checkpoints — falls back to memory/SQLite",
    config: "REDIS_ENABLED · infrastructure/k8s/redis.yaml",
  },
  {
    name: "Ollama",
    status: "Required (local)",
    description: "Local LLM + embeddings — mistral / llama3.x + nomic-embed-text",
    config: "OLLAMA_BASE_URL :11434",
  },
  {
    name: "ChromaDB",
    status: "Required",
    description: "Vector store for RAG collections (runbooks, incidents, architecture, resolved)",
    config: "CHROMA_HOST :8000 (Minikube port-forward)",
  },
  {
    name: "ServiceNow",
    status: "Placeholder",
    description: "Config fields present; ticket creation from anomaly watch planned",
    config: "SERVICENOW_URL · user/password in .env",
  },
  {
    name: "Slack",
    status: "Optional",
    description: "Webhook notifications for escalations",
    config: "SLACK_WEBHOOK_URL",
  },
  {
    name: "Confluence / ArgoCD",
    status: "Placeholder",
    description: "Integration hooks in config for future knowledge sync and deploy context",
    config: "CONFLUENCE_* · ARGOCD_*",
  },
];

export const SECURITY_ITEMS = {
  implemented: [
    "Local-first default — Ollama runs on-prem; no external API calls unless opted in",
    "ALLOW_EXTERNAL_LLM=false by default — blocks Gemini/Claude tiers",
    "sanitizer.py redacts IPs, hostnames, tokens, K8s secrets before external LLM calls",
    "LLM audit logging via audit_logger (external calls)",
    "Append-only execution audit trail — GET /api/v1/audit/executions (SQLite)",
    "ExecutorAgent write tools gated by interrupt_before + human approval API",
    "Explicit deny list for destructive kubectl operations",
    "CORS restricted to localhost dev origins by default",
  ],
  planned: [
    "Dedicated Kubernetes ServiceAccount with minimal RBAC for ExecutorAgent",
    "SIEM/CloudWatch routing for audit and LLM logs",
    "OAuth/SAML SSO for enterprise UI",
    "ServiceNow ticket sync with approval workflow",
    "SOC2-style retention policies for audit SQLite",
    "Network policies isolating backend from cluster admin APIs in production",
  ],
};

export const API_GROUPS = [
  {
    domain: "Health & Ops",
    endpoints: [
      { method: "GET", path: "/health", desc: "Backend + Ollama health" },
      { method: "GET", path: "/metrics", desc: "Prometheus scrape endpoint" },
      { method: "GET", path: "/api/v1/events/health", desc: "Kafka + SSE subscriber status" },
    ],
  },
  {
    domain: "Incidents & Triage",
    endpoints: [
      { method: "POST", path: "/api/v1/triage", desc: "Manual alert triage (TriageAgent)" },
      { method: "POST", path: "/api/v1/webhook/alertmanager", desc: "AlertManager webhook receiver" },
      { method: "GET", path: "/api/v1/webhook/alertmanager/recent", desc: "Recent auto-triaged alerts" },
      { method: "POST", path: "/api/v1/ask", desc: "Supervisor — classifies intent, routes to specialist" },
    ],
  },
  {
    domain: "Real-time Events (SSE)",
    endpoints: [
      { method: "GET", path: "/api/v1/events/incidents/stream", desc: "Live triaged incident feed" },
      { method: "GET", path: "/api/v1/events/anomalies/stream", desc: "Proactive anomaly watch feed" },
      { method: "GET", path: "/api/v1/events/stream", desc: "Unified incidents + anomalies" },
    ],
  },
  {
    domain: "Execution & Learning",
    endpoints: [
      { method: "POST", path: "/api/v1/incidents/{id}/execute", desc: "Start LangGraph executor" },
      { method: "POST", path: "/api/v1/incidents/{id}/approve/{exec_id}", desc: "Resume after approval gate" },
      { method: "GET", path: "/api/v1/incidents/{id}/execution/{exec_id}", desc: "Poll scratchpad status" },
      { method: "POST", path: "/api/v1/incidents/{id}/resolve", desc: "Mark resolved → LearningAgent" },
      { method: "GET", path: "/api/v1/audit/executions", desc: "Executor audit log entries" },
    ],
  },
  {
    domain: "Knowledge & Chat",
    endpoints: [
      { method: "POST", path: "/api/v1/chat", desc: "On-call Q&A (ChatAgent)" },
      { method: "POST", path: "/api/v1/chat/stream", desc: "Streaming chat tokens" },
      { method: "POST", path: "/api/v1/runbook/execute", desc: "Interactive runbook steps" },
      { method: "POST", path: "/api/v1/rca", desc: "Root cause analysis" },
      { method: "POST", path: "/api/v1/ingest", desc: "Re-ingest knowledge base" },
    ],
  },
  {
    domain: "Observability",
    endpoints: [
      { method: "GET", path: "/api/v1/observability/services", desc: "Live service list" },
      { method: "GET", path: "/api/v1/observability/watch", desc: "Proactive anomaly summary" },
      { method: "GET", path: "/api/v1/observability/metrics/{service}", desc: "Prometheus metrics panel data" },
      { method: "GET", path: "/api/v1/observability/logs/{service}", desc: "Loki log tail" },
      { method: "POST", path: "/api/v1/incident/analyze", desc: "Streaming telemetry analysis" },
    ],
  },
];

export const MERMAID = {
  systemContext: `flowchart TB
    subgraph Users["Users"]
      SRE["SRE / On-call Engineer"]
      MGR["Platform / Engineering Manager"]
    end

    subgraph External["External Systems"]
      AM["AlertManager"]
      PROM["Prometheus"]
      LOKI["Loki"]
      K8S["Kubernetes Cluster"]
      SN["ServiceNow (planned)"]
    end

    subgraph Copilot["SRE AI Copilot"]
      UI["React Frontend :5173"]
      API["FastAPI Backend :8080"]
      AGENTS["Multi-Agent Orchestrator"]
    end

    subgraph Data["Data & AI"]
      OLLAMA["Ollama (local LLM)"]
      CHROMA["ChromaDB (RAG)"]
      REDIS["Redis (optional)"]
      KAFKA["Kafka (optional)"]
    end

    SRE --> UI
    MGR --> UI
    UI <-->|REST + SSE| API
    AM -->|webhook| API
    PROM --> AM
    PROM --> API
    LOKI --> API
    K8S --> PROM
    AGENTS --> OLLAMA
    AGENTS --> CHROMA
    API --> AGENTS
    API --> REDIS
    API --> KAFKA
    KAFKA -.->|fan-out| UI
    API -.->|tickets planned| SN`,

  containers: `flowchart LR
    subgraph Frontend["Frontend Layer"]
      CC["Command Center"]
      OBS["Observe / Anomaly Watch"]
      INC["Incidents"]
      RB["Playbooks"]
      CHAT["ChatWidget"]
    end

    subgraph Backend["Backend Layer"]
      RTR["Routers"]
      SUP["SupervisorAgent"]
      TRI["TriageAgent"]
      EXE["ExecutorAgent (LangGraph)"]
      LRNG["LearningAgent"]
      SSE["live_events + kafka_bus"]
    end

    subgraph Stores["Stores"]
      MEM["Session / Dedup"]
      CP["Checkpoints SQLite/Redis"]
      AUD["Audit SQLite"]
      VEC["ChromaDB"]
    end

    subgraph Observability["Observability Stack"]
      PR["Prometheus"]
      LK["Loki"]
      AW["anomaly_watcher"]
    end

    CC & OBS & INC & RB & CHAT --> RTR
    RTR --> SUP
    SUP --> TRI & EXE
    EXE --> LRNG
    TRI --> VEC
    EXE --> CP
    EXE --> AUD
    RTR --> MEM
    AW --> PR
    AW --> SSE
    TRI --> SSE
    SSE --> OBS & INC`,

  incidentLifecycle: `sequenceDiagram
    autonumber
    participant Pod as Demo Pod
    participant Prom as Prometheus
    participant AM as AlertManager
    participant API as FastAPI
    participant Triage as TriageAgent
    participant RAG as ChromaDB RAG
    participant Kafka as Kafka (opt)
    participant SSE as SSE Stream
    participant UI as React UI
    participant Exec as ExecutorAgent
    participant Learn as LearningAgent

    Pod->>Prom: OOMKilled / metric breach
    Prom->>AM: Fire alert rule
    AM->>API: POST /webhook/alertmanager
    API->>Triage: Background triage
    Triage->>RAG: Similar incidents (k=3)
    RAG-->>Triage: Runbook context
    Triage-->>API: P1/P2/P3 + suggested fix
    API->>SSE: broadcast incident
    opt Kafka enabled
      API->>Kafka: publish sre.incidents.triage
      Kafka->>SSE: consumer fan-out
    end
    SSE-->>UI: EventSource update
    UI->>UI: Incidents page / badges
    alt Human approves fix
      UI->>API: POST /incidents/{id}/execute
      API->>Exec: LangGraph ReAct loop
      Exec->>Exec: gather pods/logs/metrics (parallel)
      Exec-->>UI: SSE scratchpad stream
      Exec->>API: interrupt_before write
      UI->>API: POST /approve/{exec_id}
      Exec->>Exec: kubectl patch/restart
    end
    UI->>API: POST /incidents/{id}/resolve
    API->>Learn: Ingest resolution
    Learn->>RAG: resolved_incidents collection`,

  alertTriageFlow: `flowchart LR
    A["Alert fires"] --> B["AlertManager webhook"]
    B --> C["TriageAgent + RAG"]
    C --> D{"Dedup store"}
    D --> E["Kafka topic (optional)"]
    D --> F["live_events broadcast"]
    E --> F
    F --> G["SSE /events/incidents/stream"]
    G --> H["UI: Incidents + nav badges"]`,

  observabilityPipeline: `flowchart TB
    subgraph Apps["Synthetic / Demo Apps"]
      JA["Java auth-service"]
      PY["Python order-service"]
    end

    subgraph Collect["Collection"]
      PR["Prometheus scrape"]
      PT["Promtail"]
      OT["OTel Collector"]
    end

    subgraph Store["Storage"]
      TSDB["Prometheus TSDB"]
      LOKI["Loki"]
    end

    subgraph SRE["SRE AI"]
      OW["anomaly_watcher"]
      OBS["/observability/* APIs"]
      UI["Observe page"]
    end

    JA & PY --> PR
    JA & PY --> PT
    JA & PY --> OT
    PR --> TSDB
    PT --> LOKI
    OT --> LOKI
    TSDB --> OW
    LOKI --> OBS
    TSDB --> OBS
    OW -->|SSE anomalies| UI
    OBS --> UI`,

  agentLoop: `flowchart TB
    START(["User / Webhook"]) --> SUP{"SupervisorAgent"}
    SUP -->|triage| T["TriageAgent"]
    SUP -->|chat| C["ChatAgent"]
    SUP -->|runbook| R["RunbookAgent"]
    SUP -->|rca| RCA["RCAAgent"]
    SUP -->|execute| E["ExecutorAgent"]

    T & C & R & RCA --> LLM["LLM Router"]
    LLM --> LOCAL["Ollama LOCAL"]
    LLM -.->|if allowed| EXT["External tiers"]

    E --> GATHER["Parallel gather: pods, logs, metrics"]
    GATHER --> REASON["Reason → Act loop"]
    REASON --> READ["Read tools (auto)"]
    REASON --> WRITE{"Write tools?"}
    WRITE -->|yes| GATE["Human approval gate"]
    GATE --> REASON
    WRITE -->|no| DONE(["Resolved"])
    DONE --> LEARN["LearningAgent → ChromaDB"]`,
};
