"""Demo status — for resume / HM tour landing (live vs mock indicator)."""

import os
from typing import Any

import httpx
from fastapi import APIRouter

from backend.config import settings

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


def _demo_mode() -> str:
    return (settings.demo_mode or os.environ.get("DEMO_MODE", "")).strip().lower()


@router.get("/status")
def demo_status() -> dict[str, Any]:
    prom_ok = False
    try:
        prom_url = settings.prometheus_url or "http://127.0.0.1:19090"
        r = httpx.get(f"{prom_url.rstrip('/')}/-/healthy", timeout=2.0)
        prom_ok = r.status_code == 200
    except Exception:
        pass

    live = prom_ok
    mode = _demo_mode()
    return {
        "mode": "live" if live else "mock",
        "live": live,
        "backend": True,
        "prometheus": prom_ok,
        "demo_mode": mode or None,
        "observe_demo": mode == "observability",
        "message": (
            "Synthetic Minikube stack connected — tour shows real metrics and incidents."
            if live
            else "Stack offline — tour still works; some panels use cached demo data."
        ),
    }
