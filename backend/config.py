from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

_DEFAULT_RECRUITER_DB = "backend/data/recruiter.db"

# NodePort URLs — stable, no kubectl port-forward needed.
# Minikube exposes Prometheus on :30090 and Loki on :30310 directly.
# These survive pod restarts and Mac sleep (minikube IP is stable per profile).
_MINIKUBE_IP = "192.168.105.3"
_HOST_PROM = f"http://{_MINIKUBE_IP}:30090"
_HOST_LOKI = f"http://{_MINIKUBE_IP}:30310"
_CLUSTER_PROM = "http://prometheus.observability.svc.cluster.local:9090"
_CLUSTER_LOKI = "http://loki.observability.svc.cluster.local:3100"


class Settings(BaseSettings):
    # ── Ollama ───────────────────────────────────────────────────────────────
    # Run natively on macOS — Metal GPU acceleration requires direct hardware access.
    ollama_base_url: str = "http://localhost:11434"
    # Primary model: triage + RAG chat — Mistral 7B Q4_K_M is best-in-class for
    # structured JSON output and instruction following at this size class.
    ollama_model: str = "mistral"
    # Fast model: executor decisions, general chat — 3b for lower latency
    ollama_fast_model: str = "llama3.2:3b"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_temperature: float = 0.1

    # ── ChromaDB ─────────────────────────────────────────────────────────────
    chroma_host: str = "localhost"
    chroma_port: int = 8000

    # ── Knowledge collection registry ────────────────────────────────────────
    # To add a new knowledge domain:
    #   1. Create backend/knowledge/<domain>/ with .md files
    #   2. Add "<domain>": "<collection_name>" here
    #   3. Run: make ingest
    knowledge_collections: dict[str, str] = {
        "incidents":          "sre_incidents",
        "runbooks":           "sre_runbooks",
        "architecture":       "sre_architecture",
        "resolved_incidents": "sre_resolved_incidents",
        # Resume-only RAG for recruiter Q&A — ingested via make ingest-profile
        "profile":            "sre_candidate_profile",
    }

    # ── LLM Routing ──────────────────────────────────────────────────────────
    # Safety gate: external LLMs are disabled by default.
    # Set allow_external_llm=true only after confirming data classification
    # policy with your security/compliance team.
    allow_external_llm: bool = False

    # API keys — only needed when allow_external_llm=true
    google_api_key: str = ""
    anthropic_api_key: str = ""

    # Routing thresholds
    # Alerts with fewer RAG hits than this are considered novel → escalate
    min_rag_hits_for_local: int = 1

    # ── App ──────────────────────────────────────────────────────────────────
    app_env: str = "development"
    log_level: str = "INFO"
    backend_cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── Observability (Prometheus + Loki) ─────────────────────────────────────
    # host: hybrid dev — backend on host, Prom/Loki via kubectl port-forward (:19090/:13100)
    # incluster: backend in Minikube — cluster DNS, no port-forward needed
    observability_mode: str = "host"
    prometheus_url: str = ""
    prometheus_ui_url: str = ""
    loki_url: str = ""
    loki_ui_url: str = ""
    # Legacy alias used by executor agent — kept in sync with loki_url
    loki_base_url: str = ""
    loki_log_window_minutes: int = 30    # how far back to look for logs
    loki_max_lines: int = 100            # max log lines per query

    # ── Integrations (Phase 3) ────────────────────────────────────────────────
    slack_webhook_url: str = ""
    servicenow_url: str = ""
    servicenow_user: str = ""
    servicenow_password: str = ""
    confluence_url: str = ""
    confluence_token: str = ""
    argocd_url: str = ""
    argocd_token: str = ""

    # PagerDuty Events API v2 routing key — set to enable auto-paging on P1
    pagerduty_routing_key: str = ""

    # API key gate for write endpoints (execute/approve/resolve/escalate).
    # When empty, dev-mode bypass is active and a warning is logged.
    api_key: str = ""

    # Minikube/cluster external IP used by observability simulate endpoints.
    # Override per-deployment so we never hard-code a developer's local IP.
    minikube_ip: str = "192.168.105.3"

    # Redis — session store, dedup cache, optional LangGraph checkpoints
    redis_enabled: bool = Field(
        default=False,
        description="Enable Redis-backed session/dedup persistence (falls back to in-memory)",
    )
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_session_ttl_seconds: int = 4 * 3600
    redis_dedup_ttl_seconds: int = 24 * 3600

    # LangGraph checkpoints — SQLite file when Redis checkpoint unavailable
    checkpoint_sqlite_path: str = "backend/data/checkpoints.db"

    # Execution audit trail (append-only SQLite)
    audit_sqlite_path: str = "backend/data/audit.db"
    audit_enabled: bool = True

    # Recruiter resume page views and feedback (SQLite)
    # Railway: mount a volume at /data and set DATA_DIR=/data → /data/recruiter.db
    data_dir: str = Field(
        default="",
        description="Persistent volume directory; recruiter DB defaults to {data_dir}/recruiter.db",
    )
    recruiter_sqlite_path: str = _DEFAULT_RECRUITER_DB

    # Admin token — protects /api/v1/recruiter/admin/stats
    # Generate: python3 -c "import secrets; print(secrets.token_urlsafe(32))"
    admin_token: str = ""

    # In-memory session store limits (dev fallback)
    session_max_count: int = 500
    session_max_history: int = 20
    session_ttl_seconds: int = 3600

    # ── Kafka (real-time event bus) ───────────────────────────────────────────
    kafka_enabled: bool = Field(default=False, description="Enable Kafka producer/consumer")
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_incident_topic: str = "sre.incidents.triage"
    kafka_anomaly_topic: str = "sre.observability.anomalies"
    kafka_consumer_group: str = "sre-ai-copilot"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @model_validator(mode="after")
    def _resolve_observability_urls(self) -> Self:
        incluster = self.observability_mode.strip().lower() == "incluster"
        if not self.prometheus_url:
            self.prometheus_url = _CLUSTER_PROM if incluster else _HOST_PROM
        if not self.loki_url:
            self.loki_url = _CLUSTER_LOKI if incluster else _HOST_LOKI
        if not self.prometheus_ui_url:
            self.prometheus_ui_url = _HOST_PROM if not incluster else self.prometheus_url
        if not self.loki_ui_url:
            self.loki_ui_url = _HOST_LOKI if not incluster else self.loki_url
        if not self.loki_base_url or self.loki_base_url == "http://localhost:3100":
            self.loki_base_url = self.loki_url
        return self

    @model_validator(mode="after")
    def _resolve_recruiter_sqlite_path(self) -> Self:
        if self.recruiter_sqlite_path != _DEFAULT_RECRUITER_DB:
            return self
        dd = (self.data_dir or "").strip()
        if dd:
            self.recruiter_sqlite_path = str(Path(dd) / "recruiter.db")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
