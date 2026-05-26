"""In-process fan-out for SSE live feeds (incidents, anomalies)."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)

STREAMS = ("incidents", "anomalies", "all")
HEARTBEAT_INTERVAL_S = 30.0

_subscribers: dict[str, set[asyncio.Queue]] = {name: set() for name in STREAMS}
_lock = asyncio.Lock()


def _targets_for_event(event_type: str) -> list[str]:
    if event_type == "incident":
        return ["incidents", "all"]
    if event_type == "anomaly":
        return ["anomalies", "all"]
    return ["all"]


async def subscribe(stream: str = "all") -> AsyncIterator[str]:
    """Yield SSE-formatted lines for one connected client on a named stream."""
    if stream not in STREAMS:
        stream = "all"
    queue: asyncio.Queue = asyncio.Queue(maxsize=256)
    async with _lock:
        _subscribers[stream].add(queue)
    logger.debug("SSE subscriber connected on %s (%d total)", stream, len(_subscribers[stream]))
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL_S)
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
    finally:
        async with _lock:
            _subscribers[stream].discard(queue)
        logger.debug("SSE subscriber disconnected on %s (%d total)", stream, len(_subscribers[stream]))


async def broadcast(event_type: str, payload: dict[str, Any]) -> None:
    """Push an event to SSE subscribers on matching streams."""
    message = {"type": event_type, **payload}
    streams = _targets_for_event(event_type)
    async with _lock:
        targets: list[asyncio.Queue] = []
        for name in streams:
            targets.extend(_subscribers[name])
    for queue in targets:
        try:
            queue.put_nowait(message)
        except asyncio.QueueFull:
            logger.warning("Dropping SSE event — subscriber queue full")


def subscriber_count(stream: str | None = None) -> int:
    """Return subscriber count for one stream, or total across all streams."""
    if stream is not None:
        return len(_subscribers.get(stream, set()))
    return sum(len(s) for s in _subscribers.values())


def subscriber_counts() -> dict[str, int]:
    """Per-stream SSE subscriber counts."""
    return {name: len(_subscribers[name]) for name in STREAMS}
