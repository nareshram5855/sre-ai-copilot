"""Server-Sent Events for real-time incident and anomaly feeds."""
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.config import get_settings
from backend.integrations import live_events
from backend.integrations.kafka_bus import is_connected
from backend.monitoring.profiler import get_integration_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/events", tags=["events"])


def _connected_payload(stream: str) -> str:
    return json.dumps({
        "type": "connected",
        "stream": stream,
        "kafka": is_connected(),
    })


def _sse_response(stream: str) -> StreamingResponse:
    async def _gen():
        yield f"data: {_connected_payload(stream)}\n\n"
        async for chunk in live_events.subscribe(stream):
            yield chunk

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/incidents/stream")
async def stream_incidents() -> StreamingResponse:
    """
    SSE stream of triaged incidents.
    Backed by Kafka when KAFKA_ENABLED=true; always fans out in-process.
    """
    return _sse_response("incidents")


@router.get("/anomalies/stream")
async def stream_anomalies() -> StreamingResponse:
    """SSE stream of observability anomalies from proactive watch."""
    return _sse_response("anomalies")


@router.get("/stream")
async def stream_all() -> StreamingResponse:
    """Unified SSE stream — incidents and anomalies."""
    return _sse_response("all")


@router.get("/health")
async def events_health() -> dict:
    cfg = get_settings()
    counts = live_events.subscriber_counts()
    integration = get_integration_status()
    return {
        "kafka_enabled": cfg.kafka_enabled,
        "kafka_connected": is_connected(),
        "redis_enabled": integration["redis_enabled"],
        "redis_connected": integration["redis_connected"],
        "session_backend": integration["session_backend"],
        "dedup_backend": integration["dedup_backend"],
        "topics": {
            "incidents": cfg.kafka_incident_topic,
            "anomalies": cfg.kafka_anomaly_topic,
        },
        "sse_subscribers": counts,
        "subscriber_count": live_events.subscriber_count(),
        "heartbeat_interval_s": live_events.HEARTBEAT_INTERVAL_S,
    }
