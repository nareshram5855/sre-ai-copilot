import httpx
from fastapi import APIRouter, Depends

from backend.config import Settings, get_settings
from backend.routers._models import HealthResponse

router = APIRouter(tags=["ops"])


@router.get("/health", response_model=HealthResponse)
def health(cfg: Settings = Depends(get_settings)):
    return {"status": "healthy", "ollama_model": cfg.ollama_model, "environment": cfg.app_env}


@router.get("/health/ollama", tags=["ops"])
def health_ollama(cfg: Settings = Depends(get_settings)):
    """Detailed Ollama health — lists loaded models and their sizes."""
    try:
        resp = httpx.get(f"{cfg.ollama_base_url}/api/tags", timeout=3)
        return {"status": "reachable", "models": resp.json().get("models", [])}
    except Exception as exc:
        return {"status": "unreachable", "error": str(exc)}
