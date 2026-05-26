"""Background poll of observability watch — emits new anomalies to Kafka/SSE."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from backend.integrations.kafka_bus import emit_anomaly

logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 30.0
_task: asyncio.Task | None = None


def _fingerprint(anomalies: list[dict]) -> frozenset[str]:
    return frozenset(
        f"{a.get('service')}:{a.get('type')}:{a.get('severity')}:{a.get('label')}"
        for a in anomalies
    )


def _anomaly_key(anomaly: dict) -> str:
    return f"{anomaly.get('service')}:{anomaly.get('type')}:{anomaly.get('severity')}:{anomaly.get('label')}"


def _fp_store():
    from backend.memory.persistence import anomaly_fingerprint_store

    return anomaly_fingerprint_store


def reset_fingerprints() -> None:
    _fp_store().reset()


async def _poll_loop() -> None:
    from backend.routers.observability import watch_summary

    # Give uvicorn time to finish startup before first blocking poll
    await asyncio.sleep(15)

    store = _fp_store()
    while True:
        try:
            result = watch_summary(minutes=10)
            anomalies = result.get("anomalies", [])
            fp = _fingerprint(anomalies)
            last_fp = store.get_fingerprints()
            new_keys = fp - last_fp
            if new_keys:
                now = datetime.now(tz=timezone.utc).isoformat()
                for anomaly in anomalies:
                    if _anomaly_key(anomaly) not in new_keys:
                        continue
                    await emit_anomaly({
                        **anomaly,
                        "detected_at": now,
                        "overall_health": result.get("overall_health"),
                        "anomaly_count": result.get("anomaly_count"),
                    })
                logger.debug("Emitted %d new anomaly event(s)", len(new_keys))
            store.set_fingerprints(fp)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Anomaly watch poll failed: %s", exc)
        await asyncio.sleep(POLL_INTERVAL_S)


async def start() -> None:
    global _task
    if _task is not None:
        return
    _task = asyncio.create_task(_poll_loop(), name="anomaly-watcher")
    logger.info("Anomaly watcher started (interval=%ss)", POLL_INTERVAL_S)


async def stop() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    _task = None
    reset_fingerprints()
