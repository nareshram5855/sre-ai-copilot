"""Lightweight in-process profiler — request latency, integration health, memory."""
from __future__ import annotations

import platform
import resource
import sys
import time
from collections import deque
from threading import Lock
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.config import get_settings

_START_MONO = time.monotonic()
_START_WALL = time.time()
_lock = Lock()
_request_count = 0
_active_requests = 0
_latencies_ms: deque[float] = deque(maxlen=2000)
_recent_requests: deque[float] = deque(maxlen=5000)

_SKIP_LATENCY_PREFIXES = ("/api/v1/events/",)


def _memory_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return round(usage / (1024 * 1024), 2)
    return round(usage / 1024, 2)


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(int(len(ordered) * pct / 100), len(ordered) - 1)
    return round(ordered[idx], 2)


def _requests_per_second(window_s: float = 60.0) -> float:
    now = time.monotonic()
    cutoff = now - window_s
    with _lock:
        while _recent_requests and _recent_requests[0] < cutoff:
            _recent_requests.popleft()
        count = len(_recent_requests)
    return round(count / window_s, 3) if window_s > 0 else 0.0


def record_request(duration_ms: float, *, track_latency: bool = True) -> None:
    global _request_count
    now = time.monotonic()
    with _lock:
        _request_count += 1
        _recent_requests.append(now)
        if track_latency:
            _latencies_ms.append(duration_ms)


def get_integration_status() -> dict[str, Any]:
    """Kafka + Redis connectivity for health and profiler dashboards."""
    from backend.integrations import kafka_bus
    from backend.integrations import live_events
    from backend.memory.persistence import get_persistence_state

    cfg = get_settings()
    state = get_persistence_state()
    redis_connected = False
    if state.redis_available and state.redis_client is not None:
        try:
            redis_connected = bool(state.redis_client.ping())
        except Exception:
            redis_connected = False

    return {
        "kafka_enabled": cfg.kafka_enabled,
        "kafka_connected": kafka_bus.is_connected(),
        "redis_enabled": cfg.redis_enabled,
        "redis_connected": redis_connected,
        "session_backend": state.session_backend,
        "dedup_backend": state.dedup_backend,
        "checkpointer_backend": state.checkpointer_backend,
        "sse_subscribers": live_events.subscriber_counts(),
        "sse_subscriber_total": live_events.subscriber_count(),
        "active_sessions": _safe_session_count(),
    }


def _safe_session_count() -> int:
    try:
        from backend.memory.persistence import session_store

        return session_store.session_count()
    except Exception:
        return -1


def build_snapshot() -> dict[str, Any]:
    cfg = get_settings()
    uptime_s = round(time.monotonic() - _START_MONO, 1)

    with _lock:
        latencies = list(_latencies_ms)
        total_requests = _request_count
        in_flight = _active_requests

    avg_ms = round(sum(latencies) / len(latencies), 2) if latencies else None

    integration = get_integration_status()

    return {
        "uptime_seconds": uptime_s,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(_START_WALL)),
        "requests": {
            "total": total_requests,
            "in_flight": in_flight,
            "per_second": _requests_per_second(),
            "latency_ms": {
                "avg": avg_ms,
                "p50": _percentile(latencies, 50),
                "p99": _percentile(latencies, 99),
                "samples": len(latencies),
            },
        },
        "runtime": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "memory_mb": _memory_mb(),
            "ollama_model": cfg.ollama_model,
            "ollama_fast_model": cfg.ollama_fast_model,
            "environment": cfg.app_env,
        },
        "integrations": integration,
    }


def render_prometheus() -> str:
    snap = build_snapshot()
    req = snap["requests"]
    lat = req["latency_ms"]
    integ = snap["integrations"]
    lines = [
        "# HELP sre_ai_uptime_seconds Process uptime in seconds.",
        "# TYPE sre_ai_uptime_seconds gauge",
        f"sre_ai_uptime_seconds {snap['uptime_seconds']}",
        "# HELP sre_ai_requests_total Total HTTP requests observed by profiler.",
        "# TYPE sre_ai_requests_total counter",
        f"sre_ai_requests_total {req['total']}",
        "# HELP sre_ai_requests_in_flight Active HTTP requests.",
        "# TYPE sre_ai_requests_in_flight gauge",
        f"sre_ai_requests_in_flight {req['in_flight']}",
        "# HELP sre_ai_requests_per_second Rolling 60s request rate.",
        "# TYPE sre_ai_requests_per_second gauge",
        f"sre_ai_requests_per_second {req['per_second']}",
        "# HELP sre_ai_memory_mb Resident set size in megabytes.",
        "# TYPE sre_ai_memory_mb gauge",
        f"sre_ai_memory_mb {snap['runtime']['memory_mb']}",
        "# HELP sre_ai_kafka_connected Kafka producer connected (1=yes).",
        "# TYPE sre_ai_kafka_connected gauge",
        f"sre_ai_kafka_connected {1 if integ['kafka_connected'] else 0}",
        "# HELP sre_ai_redis_connected Redis ping succeeded (1=yes).",
        "# TYPE sre_ai_redis_connected gauge",
        f"sre_ai_redis_connected {1 if integ['redis_connected'] else 0}",
        "# HELP sre_ai_sse_subscribers Active SSE subscribers.",
        "# TYPE sre_ai_sse_subscribers gauge",
        f"sre_ai_sse_subscribers {integ['sse_subscriber_total']}",
    ]
    if lat["p50"] is not None:
        lines.extend([
            "# HELP sre_ai_request_latency_p50_ms 50th percentile request latency.",
            "# TYPE sre_ai_request_latency_p50_ms gauge",
            f"sre_ai_request_latency_p50_ms {lat['p50']}",
        ])
    if lat["p99"] is not None:
        lines.extend([
            "# HELP sre_ai_request_latency_p99_ms 99th percentile request latency.",
            "# TYPE sre_ai_request_latency_p99_ms gauge",
            f"sre_ai_request_latency_p99_ms {lat['p99']}",
        ])
    return "\n".join(lines) + "\n"


class ProfilerMiddleware(BaseHTTPMiddleware):
    """Track request counts and latency (excluding long-lived SSE streams)."""

    async def dispatch(self, request: Request, call_next) -> Response:
        global _active_requests
        path = request.url.path
        skip_latency = path.startswith(_SKIP_LATENCY_PREFIXES)
        skip_count = path in ("/api/v1/profiler", "/api/v1/metrics")

        if not skip_count:
            with _lock:
                _active_requests += 1
        start = time.perf_counter()
        try:
            return await call_next(request)
        finally:
            if not skip_count:
                duration_ms = (time.perf_counter() - start) * 1000
                record_request(duration_ms, track_latency=not skip_latency)
                with _lock:
                    _active_requests -= 1
