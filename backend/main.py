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
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from backend.config import get_settings
from backend.monitoring.profiler import ProfilerMiddleware
from backend.routers import agent_react, agent_run, alertmanager, audit, chat, demo, docs, events, execute, health, incident_analysis, incidents, knowledge, observability, profiler, rca, recruiter, runbook, triage, stackport_demo, stackport_ai
from backend.voice.config import get_voice_settings
from backend.voice import router as voice_router

logging.basicConfig(
    level=get_settings().log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.integrations import anomaly_watcher, kafka_bus
    from backend.memory.persistence import init_persistence

    init_persistence()
    await kafka_bus.start()
    await anomaly_watcher.start()
    _startup_checks()
    _ensure_profile_rag()
    yield
    await anomaly_watcher.stop()
    await kafka_bus.stop()


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


def _ensure_profile_rag() -> None:
    """Index resume content for recruiter RAG when the profile collection is empty."""
    import threading
    from backend.knowledge.profile_ingest import ensure_profile_ingested

    def _ingest():
        try:
            ensure_profile_ingested()
        except Exception as exc:
            logger.warning("Profile RAG auto-ingest failed: %s — run: make ingest-profile", exc)

    threading.Thread(target=_ingest, daemon=True).start()


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
app.add_middleware(ProfilerMiddleware)

Instrumentator().instrument(app).expose(app)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(health.router)
app.include_router(profiler.router)
app.include_router(triage.router)
app.include_router(knowledge.router)
app.include_router(chat.router)
app.include_router(runbook.router)
app.include_router(rca.router)
app.include_router(alertmanager.router)
app.include_router(events.router)
app.include_router(incidents.router)
app.include_router(execute.router)
app.include_router(audit.router)
app.include_router(agent_run.router)
app.include_router(agent_react.router)

# ── Voice Module (Optional Plugin) ────────────────────────────────────────────
# Only registered if explicitly enabled via config. Zero impact if disabled.
if get_voice_settings().voice_enabled:
    app.include_router(voice_router.router)
    logger.info("Voice module enabled ✓")
app.include_router(incident_analysis.router)
app.include_router(observability.router)
app.include_router(docs.router)
app.include_router(recruiter.router)
app.include_router(demo.router)
app.include_router(stackport_demo.router)
app.include_router(stackport_ai.router)

# ── Static frontend (production / Railway) ────────────────────────────────────
# Served only when the React build exists (i.e. in Docker / after npm run build).
# In local dev, Vite's dev server handles the frontend instead.
import os as _os
from fastapi.responses import FileResponse
_dist = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", "frontend", "dist"))
if _os.path.isdir(_dist):
    from fastapi.staticfiles import StaticFiles

    # ── Stackport demo at /stackport/* ──────────────────────────────────────────
    _sp_dist = _os.path.join(_dist, "stackport")
    if _os.path.isdir(_sp_dist):
        _sp_assets = _os.path.join(_sp_dist, "assets")
        if _os.path.isdir(_sp_assets):
            app.mount("/stackport/assets", StaticFiles(directory=_sp_assets), name="stackport-assets")

        # Explicit route for /stackport (no trailing slash) — path params need ≥1 char
        @app.get("/stackport", include_in_schema=False)
        async def serve_stackport_root():
            return FileResponse(_os.path.join(_sp_dist, "index.html"))

        @app.get("/stackport/{sp_path:path}", include_in_schema=False)
        async def serve_stackport(sp_path: str):
            if sp_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not Found")
            candidate = _os.path.normpath(_os.path.join(_sp_dist, sp_path))
            if candidate.startswith(_sp_dist) and _os.path.isfile(candidate):
                return FileResponse(candidate)
            return FileResponse(_os.path.join(_sp_dist, "index.html"))

        logger.info("Serving Stackport demo from frontend/dist/stackport")

    # Serve fingerprinted assets (JS/CSS/fonts) directly; fall back to index.html
    # for all other paths so React Router can handle client-side navigation.
    # NOTE: this catch-all MUST come after all API routers are registered.
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        # Never let the catch-all swallow Stackport paths
        if full_path == "stackport" or full_path.startswith("stackport/"):
            sp_dist = _os.path.join(_dist, "stackport")
            if _os.path.isdir(sp_dist):
                sp_rel = full_path[len("stackport/"):] if full_path.startswith("stackport/") else ""
                c = _os.path.normpath(_os.path.join(sp_dist, sp_rel)) if sp_rel else None
                if c and c.startswith(sp_dist) and _os.path.isfile(c):
                    return FileResponse(c)
                return FileResponse(_os.path.join(sp_dist, "index.html"))
        # Serve the real file if it exists (assets, favicon, etc.)
        candidate = _os.path.normpath(_os.path.join(_dist, full_path))
        if candidate.startswith(_dist) and _os.path.isfile(candidate):
            return FileResponse(candidate)
        # SPA fallback — portfolio app
        return FileResponse(_os.path.join(_dist, "index.html"))

    # Mount /assets specifically so fingerprinted JS/CSS are also served via
    # the StaticFiles handler (handles ETags, range requests, etc.) in addition
    # to the catch-all above.
    _assets_dir = _os.path.join(_dist, "assets")
    if _os.path.isdir(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="static-assets")

    logger.info("Serving React SPA from frontend/dist")

# ── Dev entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8080, reload=True)
