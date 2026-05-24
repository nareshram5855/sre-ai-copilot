from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


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

    # ── Loki ─────────────────────────────────────────────────────────────────
    # Logs must be fetched from Loki, never via kubectl logs directly.
    # Port-forward: kubectl port-forward svc/loki 3100:3100 -n monitoring
    loki_base_url: str = "http://localhost:3100"
    loki_log_window_minutes: int = 30    # how far back to look for logs
    loki_max_lines: int = 100            # max log lines per query

    # ── Integrations (Phase 3) ────────────────────────────────────────────────
    prometheus_url: str = "http://localhost:9090"
    slack_webhook_url: str = ""
    servicenow_url: str = ""
    servicenow_user: str = ""
    servicenow_password: str = ""
    confluence_url: str = ""
    confluence_token: str = ""
    argocd_url: str = ""
    argocd_token: str = ""

    # Redis — used by RedisSessionStore when configured
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
