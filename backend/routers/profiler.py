"""Application profiler — JSON dashboard + Prometheus self-metrics."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from backend.monitoring.profiler import build_snapshot, render_prometheus

router = APIRouter(prefix="/api/v1", tags=["profiler"])


@router.get("/profiler")
def profiler_dashboard() -> dict[str, Any]:
    """Runtime stats for the App Profiler UI."""
    return build_snapshot()


@router.get("/metrics", response_class=PlainTextResponse)
def profiler_metrics() -> PlainTextResponse:
    """Prometheus text format — app-level counters/gauges (distinct from /metrics instrumentator)."""
    return PlainTextResponse(render_prometheus(), media_type="text/plain; version=0.0.4")
