"""Demo status — for resume / HM tour landing (live vs mock indicator)."""

from typing import Any

import httpx
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


@router.get("/status")
def demo_status() -> dict[str, Any]:
    prom_ok = False
    try:
        r = httpx.get("http://127.0.0.1:19090/-/healthy", timeout=2.0)
        prom_ok = r.status_code == 200
    except Exception:
        pass

    live = prom_ok
    return {
        "mode": "live" if live else "mock",
        "live": live,
        "backend": True,
        "prometheus": prom_ok,
        "message": (
            "Synthetic Minikube stack connected — tour shows real metrics and incidents."
            if live
            else "Stack offline — tour still works; some panels use cached demo data."
        ),
    }
