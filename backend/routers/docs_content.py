"""Architecture documentation content — Python mirror of frontend docsContent.js."""

DOC_SECTIONS = [
    {"id": "summary", "label": "Executive Summary"},
    {"id": "tech-stack", "label": "Tech Stack"},
    {"id": "architecture", "label": "Architecture Overview"},
    {"id": "data-flows", "label": "Data Flows"},
    {"id": "components", "label": "Component Map"},
    {"id": "integrations", "label": "Integration Points"},
    {"id": "security", "label": "Security & Compliance"},
    {"id": "deployment", "label": "Deployment Topology"},
    {"id": "api", "label": "API Overview"},
]

TECH_STACK = [
    {"layer": "Frontend", "technology": "React 18 · Vite 6 · TailwindCSS", "role": "Command Center, Observe, Incidents, Playbooks, AI Analysis, ChatWidget", "status": "Shipped"},
    {"layer": "Backend", "technology": "FastAPI · Python 3.11+ · Uvicorn", "role": "REST + SSE APIs, webhook receiver, Prometheus instrumentation", "status": "Shipped"},
    {"layer": "AI / Agents", "technology": "LangGraph 0.2 · LangChain · Ollama", "role": "Triage, Chat, Runbook, RCA, Executor, Supervisor, Learning agents", "status": "Shipped"},
    {"layer": "RAG / Memory", "technology": "ChromaDB · nomic-embed-text · Redis (optional)", "role": "Runbook/incident retrieval; session, dedup, LangGraph checkpoints", "status": "Shipped"},
    {"layer": "Observability", "technology": "Prometheus · Loki · Promtail · OTel · Grafana", "role": "Metrics, logs, synthetic stack, proactive anomaly watch", "status": "Shipped"},
    {"layer": "Event Bus", "technology": "Kafka (aiokafka) + in-process SSE", "role": "Durable incident/anomaly feeds; UI EventSource streams", "status": "Shipped (opt-in)"},
    {"layer": "Storage", "technology": "ChromaDB · SQLite checkpoints/audit · Redis", "role": "Knowledge vectors, executor audit trail, session persistence", "status": "Shipped"},
]

COMPONENT_MAP = [
    {"path": "frontend/src/", "purpose": "React SPA — enterprise dark UI", "modules": ["App.jsx", "components/", "hooks/"]},
    {"path": "backend/agents/", "purpose": "Specialist LLM agents", "modules": ["triage_agent", "executor_agent", "supervisor_agent", "learning_agent"]},
    {"path": "backend/integrations/", "purpose": "Kafka, SSE, anomaly watcher", "modules": ["kafka_bus.py", "live_events.py", "anomaly_watcher.py"]},
    {"path": "backend/memory/", "purpose": "Redis/SQLite persistence", "modules": ["persistence.py", "audit_store.py", "redis_store.py"]},
]

INTEGRATIONS = [
    {"name": "Prometheus", "status": "Connected", "description": "Metrics + AlertManager webhook source", "config": "PROMETHEUS_URL"},
    {"name": "Kafka", "status": "Optional", "description": "Incident/anomaly topics with SSE fallback", "config": "KAFKA_ENABLED"},
    {"name": "Redis", "status": "Optional", "description": "Session, dedup, checkpoints", "config": "REDIS_ENABLED"},
    {"name": "ServiceNow", "status": "Placeholder", "description": "Ticket integration planned", "config": "SERVICENOW_URL"},
]

SECURITY_ITEMS = {
    "implemented": [
        "Local-first Ollama default",
        "ALLOW_EXTERNAL_LLM=false by default",
        "sanitizer.py for external LLM payloads",
        "Append-only execution audit trail",
        "ExecutorAgent human approval gates",
    ],
    "planned": [
        "Kubernetes RBAC ServiceAccount for executor",
        "SSO / OAuth for UI",
        "SIEM audit log routing",
        "ServiceNow approval workflow",
    ],
}

API_GROUPS = [
    {
        "domain": "Incidents & Triage",
        "endpoints": [
            {"method": "POST", "path": "/api/v1/triage", "desc": "Manual alert triage"},
            {"method": "POST", "path": "/api/v1/webhook/alertmanager", "desc": "AlertManager webhook"},
            {"method": "GET", "path": "/api/v1/events/incidents/stream", "desc": "SSE incident feed"},
        ],
    },
    {
        "domain": "Execution & Audit",
        "endpoints": [
            {"method": "POST", "path": "/api/v1/incidents/{id}/execute", "desc": "Start LangGraph executor"},
            {"method": "GET", "path": "/api/v1/audit/executions", "desc": "Audit log entries"},
        ],
    },
]

MERMAID = {
    "systemContext": "flowchart TB\n  SRE[On-call Engineer] --> UI[React Frontend]\n  UI <--> API[FastAPI Backend]\n  AM[AlertManager] --> API\n  API --> AGENTS[Multi-Agent System]\n  AGENTS --> OLLAMA[Ollama]\n  AGENTS --> CHROMA[ChromaDB]",
    "containers": "flowchart LR\n  UI[Frontend] --> RTR[Routers]\n  RTR --> AGENTS[Agents]\n  AGENTS --> VEC[ChromaDB]\n  AGENTS --> SSE[SSE/Kafka]",
    "incidentLifecycle": "sequenceDiagram\n  AM->>API: webhook\n  API->>Triage: classify\n  Triage->>UI: SSE broadcast\n  UI->>API: execute/approve\n  API->>Learn: resolve",
}
