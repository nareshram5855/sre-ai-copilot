import httpx
from fastapi import APIRouter, Depends
from typing import Any

from backend.config import Settings, get_settings
from backend.monitoring.profiler import get_integration_status
from backend.routers.observability import observability_remediation

router = APIRouter(tags=["ops"])


@router.get("/health")
def health(cfg: Settings = Depends(get_settings)) -> dict[str, Any]:
    integration = get_integration_status()
    body: dict[str, Any] = {
        "status": "healthy",
        "ollama_model": cfg.ollama_model,
        "environment": cfg.app_env,
        "kafka_enabled": integration["kafka_enabled"],
        "kafka_connected": integration["kafka_connected"],
        "redis_enabled": integration["redis_enabled"],
        "redis_connected": integration["redis_connected"],
        "session_backend": integration["session_backend"],
        "dedup_backend": integration["dedup_backend"],
        "checkpointer_backend": integration["checkpointer_backend"],
    }
    remediation = observability_remediation()
    if remediation:
        body["observability"] = "degraded"
        body["remediation"] = remediation
    else:
        body["observability"] = "ok"
    return body


@router.get("/health/ollama", tags=["ops"])
def health_ollama(cfg: Settings = Depends(get_settings)):
    """Detailed Ollama health — lists loaded models and their sizes."""
    try:
        resp = httpx.get(f"{cfg.ollama_base_url}/api/tags", timeout=3)
        return {"status": "reachable", "models": resp.json().get("models", [])}
    except Exception as exc:
        return {"status": "unreachable", "error": str(exc)}
