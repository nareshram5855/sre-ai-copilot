"""
SRE AI Copilot — FastAPI entry point.

This file only does three things:
  1. Creates the app
  2. Registers routers
  3. Handles lifespan (startup checks)

All route logic lives in backend/routers/. Adding a new agent:
  - Write backend/agents/your_agent.py  (extends BaseAgent)
  - Write backend/routers/your_router.py
  - Add: app.include_router(your_router.router) below

Port layout:
  :11434  Ollama   (native macOS — Metal GPU)
  :8000   ChromaDB (Minikube, port-forwarded)
  :8080   This API (native Python venv, hot reload)
  :5173   React    (Vite, HMR)
"""
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from backend.config import get_settings
from backend.routers import agent_react, agent_run, alertmanager, chat, execute, health, incident_analysis, incidents, knowledge, observability, rca, runbook, triage
from backend.voice.config import get_voice_settings
from backend.voice import router as voice_router

logging.basicConfig(
    level=get_settings().log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _startup_checks()
    yield


def _startup_checks() -> None:
    cfg = get_settings()
    try:
        resp = httpx.get(f"{cfg.ollama_base_url}/api/tags", timeout=3)
        loaded = [m["name"] for m in resp.json().get("models", [])]
        if not any(cfg.ollama_model in m for m in loaded):
            logger.warning("Model '%s' not found. Run: ollama pull %s", cfg.ollama_model, cfg.ollama_model)
        else:
            logger.info("Ollama ready — model '%s' loaded.", cfg.ollama_model)
            _warmup_executor_cache(cfg)
    except Exception:
        logger.warning("Ollama unreachable at %s. Run: ollama serve", cfg.ollama_base_url)


def _warmup_executor_cache(cfg) -> None:
    """
    Pre-cache the executor's static system message in Ollama's KV cache.
    After this call, the first real incident's LLM step costs ~3s instead of ~7s
    because Ollama won't need to re-encode the 250-token static system prefix.
    """
    import threading
    from backend.agents.executor_agent import _SYSTEM_STATIC, _HTTP

    def _warm():
        try:
            _HTTP.post(
                f"{cfg.ollama_base_url}/api/chat",
                json={
                    "model": cfg.ollama_model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_STATIC},
                        {"role": "user",   "content": "Warmup. Output: {\"thought\":\"\",\"action\":\"\",\"args\":{},\"done\":true,\"escalate\":false}"},
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {"num_ctx": 2048, "num_predict": 30, "temperature": 0.0},
                },
                timeout=30,
            )
            logger.info("Executor KV cache warmed up.")
        except Exception as exc:
            logger.warning("Executor warmup failed (non-fatal): %s", exc)

    threading.Thread(target=_warm, daemon=True, name="executor-warmup").start()


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="SRE AI Copilot",
    description="Local LLM-powered SRE platform — no external APIs required",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(health.router)
app.include_router(triage.router)
app.include_router(knowledge.router)
app.include_router(chat.router)
app.include_router(runbook.router)
app.include_router(rca.router)
app.include_router(alertmanager.router)
app.include_router(incidents.router)
app.include_router(execute.router)
app.include_router(agent_run.router)
app.include_router(agent_react.router)

# ── Voice Module (Optional Plugin) ────────────────────────────────────────────
# Only registered if explicitly enabled via config. Zero impact if disabled.
if get_voice_settings().voice_enabled:
    app.include_router(voice_router.router)
    logger.info("Voice module enabled ✓")
app.include_router(incident_analysis.router)
app.include_router(observability.router)

# ── Dev entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8080, reload=True)
