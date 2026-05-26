/**
 * Single-page architecture explainer — /resume featured project section.
 * Reuses TECH_STACK_COMPARISON framing from resumeContent.js where imported.
 * Aligned with EnterpriseDocsPage / docsContent observability pipeline narrative.
 */

export const ARCHITECTURE_SECTIONS = [
  { id: "architecture-sixty", label: "60-second summary" },
  { id: "architecture-diagram", label: "Architecture diagram" },
  { id: "architecture-flow", label: "End-to-end flow" },
  { id: "architecture-components", label: "Component map" },
  { id: "architecture-stack", label: "Tool stack" },
  { id: "architecture-enterprise", label: "Enterprise benefits" },
];

/** Plain-language recap for hiring managers — no jargon wall. */
export const SIXTY_SECOND_SUMMARY = {
  headline: "How it works in 60 seconds",
  intro:
    "An AI copilot for on-call engineers: it connects alerts, live telemetry, and runbooks in one screen — then helps triage and fix incidents with human approval on every risky action.",
  bullets: [
    {
      label: "Problem",
      text: "Metrics, logs, and traces usually live in separate tools. Context gets lost while engineers jump between tabs.",
    },
    {
      label: "Approach",
      text: "One Command Center pulls Prometheus metrics, Loki logs, and OTEL traces together — then AI agents classify alerts and suggest fixes from your runbooks.",
    },
    {
      label: "Safety",
      text: "Destructive changes wait for explicit human approval. Every action is logged for audit and post-incident review.",
    },
    {
      label: "Outcome",
      text: "Faster time-to-context and shorter MTTR — without sacrificing the guardrails enterprises require.",
    },
  ],
};

export const INCIDENT_FLOW_STEPS = [
  {
    id: "webhook",
    step: 1,
    title: "AlertManager webhook",
    short: "Webhook",
    detail:
      "Prometheus rules fire → AlertManager POSTs to FastAPI. Fingerprints deduplicated in Redis before an incident record is created.",
    tech: "Prometheus · AlertManager · Redis dedup",
    accent: "amber",
  },
  {
    id: "observe",
    step: 2,
    title: "Unified Observe pane",
    short: "Observe",
    detail:
      "Prometheus metrics, Loki logs, and OTEL traces and events surface in one Command Center view — no tab-hopping between consoles during triage.",
    tech: "Prometheus · Loki · OTel · /observability APIs",
    accent: "emerald",
  },
  {
    id: "triage",
    step: 3,
    title: "Triage agent",
    short: "Triage",
    detail:
      "LangGraph TriageAgent classifies severity (P1/P2/P3), extracts service context, and routes to the Command Center incident queue.",
    tech: "LangGraph · TriageAgent",
    accent: "indigo",
  },
  {
    id: "sse",
    step: 4,
    title: "Command Center live feed",
    short: "Live feed",
    detail:
      "Kafka durable fan-out with SSE fallback pushes fleet health, anomaly counts, and new incidents to the React dashboard in real time.",
    tech: "Kafka · SSE · live events API",
    accent: "teal",
  },
  {
    id: "analysis",
    step: 5,
    title: "AI analysis",
    short: "Analysis",
    detail:
      "AnalysisAgent pulls live Prometheus metrics, Loki log context, and OTEL trace signals, then produces structured RCA — root cause, confidence, and recommended fix.",
    tech: "Prometheus · Loki · OTEL · AnalysisAgent",
    accent: "indigo",
  },
  {
    id: "rag",
    step: 6,
    title: "RAG runbook match",
    short: "RAG",
    detail:
      "ChromaDB vector search retrieves the closest runbook chunk. RunbookAgent maps symptoms to remediation steps with risk classification.",
    tech: "ChromaDB · RunbookAgent · Ollama",
    accent: "violet",
  },
  {
    id: "approval",
    step: 7,
    title: "Human approval gate",
    short: "Approval",
    detail:
      "Destructive kubectl actions require explicit operator approval — mirrors enterprise change boards. Read-only gathers run in parallel first.",
    tech: "Human-in-the-loop · ExecutorAgent",
    accent: "emerald",
  },
  {
    id: "remediation",
    step: 8,
    title: "kubectl remediation",
    short: "Remediate",
    detail:
      "ExecutorAgent runs approved plans against Minikube synthetic microservices — scale, restart, rollback — with live output streamed to the UI.",
    tech: "kubectl · K8s API · synthetic fleet",
    accent: "teal",
  },
  {
    id: "audit",
    step: 9,
    title: "Audit log",
    short: "Audit",
    detail:
      "Every agent action, approval, and kubectl command appended to SQLite audit store — SOX-ready evidence for post-incident review.",
    tech: "SQLite audit · append-only",
    accent: "amber",
  },
];

export const COMPONENT_LAYERS = [
  {
    id: "frontend",
    title: "Frontend",
    icon: "layout",
    summary: "React 18 SPA — Command Center, unified Observe pane, incidents, analysis, playbooks, audit.",
    items: [
      "Vite · TailwindCSS · dark enterprise theme",
      "SSE hooks for live fleet health & incidents",
      "Metrics · logs · traces · OTEL in one Observe view",
    ],
    accent: "indigo",
  },
  {
    id: "backend",
    title: "Backend / API",
    icon: "server",
    summary: "FastAPI with role-based auth, webhook ingestion, and streaming endpoints.",
    items: [
      "REST + SSE · API-key middleware",
      "AlertManager · observability · execute routers",
      "Gunicorn · nginx reverse proxy ready",
    ],
    accent: "teal",
  },
  {
    id: "agents",
    title: "Agents (LangGraph)",
    icon: "brain",
    summary: "Seven specialist agents orchestrated with checkpointing and supervisor routing.",
    items: [
      "Triage · Chat · Runbook · RCA · Executor · Supervisor · Learning",
      "LangGraph state machine · Redis/SQLite checkpoints",
      "Ollama local LLM · structured JSON outputs",
    ],
    accent: "violet",
  },
  {
    id: "data",
    title: "Data layer",
    icon: "database",
    summary: "Polyglot persistence — vector search, sessions, dedup, and audit.",
    items: [
      "ChromaDB — RAG runbook embeddings",
      "Redis — sessions · dedup · LangGraph checkpoints",
      "SQLite — audit trail · recruiter analytics",
    ],
    accent: "amber",
  },
  {
    id: "observability",
    title: "Observability",
    icon: "activity",
    summary: "Unified metrics, logs, traces, and OTEL events — collected once, viewed in one pane.",
    items: [
      "Prometheus · Loki · Promtail · OTel collector",
      "Anomaly watcher · fleet health aggregation",
      "Kafka incident/anomaly fan-out · SSE fallback",
    ],
    accent: "emerald",
  },
  {
    id: "infra",
    title: "Infrastructure",
    icon: "cloud",
    summary: "Minikube cluster with 7 synthetic microservices and GitHub Actions CD.",
    items: [
      "Kubernetes manifests · Helm-ready patterns",
      "7 synthetic services (auth, order, gateway, …)",
      "GitHub Actions CD · Makefile automation",
    ],
    accent: "sky",
  },
];

export const TOOL_STACK_CATEGORIES = [
  {
    category: "UI & experience",
    tools: ["React 18", "Vite", "TailwindCSS", "Lucide icons", "SSE client"],
  },
  {
    category: "API & runtime",
    tools: ["FastAPI", "Python 3.11+", "Gunicorn", "Uvicorn", "nginx"],
  },
  {
    category: "AI & orchestration",
    tools: ["LangGraph", "LangChain", "Ollama", "Claude API (optional)", "RAG pipeline"],
  },
  {
    category: "Data & messaging",
    tools: ["ChromaDB", "Redis", "SQLite", "Kafka (aiokafka)", "LangGraph checkpoints"],
  },
  {
    category: "Observability",
    tools: ["Prometheus", "Loki", "Promtail", "OTel collector", "AlertManager"],
  },
  {
    category: "Platform & delivery",
    tools: ["Kubernetes", "Minikube", "Docker", "GitHub Actions", "Make automation"],
  },
];

export const ENTERPRISE_BENEFITS = [
  {
    title: "Incident record automation",
    enterprise: "Elasticsearch + Netcool dedup → auto incident tickets at Citi/BofA scale",
    demo: "AlertManager webhook → deduped incident queue with P1/P2/P3 triage",
    icon: "ticket",
  },
  {
    title: "Event deduplication",
    enterprise: "Netcool fingerprinting prevents duplicate pages for same root cause",
    demo: "Redis dedup store + Kafka durable fan-out with SSE fallback",
    icon: "filter",
  },
  {
    title: "Human-in-the-loop change boards",
    enterprise: "CAB approval before prod kubectl/Terraform writes",
    demo: "ExecutorAgent gates destructive actions — operator must approve in UI",
    icon: "shield",
  },
  {
    title: "SOX audit trail",
    enterprise: "IAM entitlement reviews · append-only compliance logs at Citi",
    demo: "SQLite audit store — who approved what, when, with full agent context",
    icon: "file",
  },
  {
    title: "MTTR reduction",
    enterprise: "Metrics, logs, and traces scattered across separate consoles — context lost in tab-hopping",
    demo: "Unified Observe pane + AI triage + RAG runbook match in one Command Center view",
    icon: "clock",
  },
  {
    title: "Unified observability at scale",
    enterprise: "Splunk · Datadog · Dynatrace silos across Fortune-scale regulated workloads",
    demo: "Prometheus + Loki + OTEL on 7 synthetic microservices — one pane, one API surface",
    icon: "chart",
  },
];
