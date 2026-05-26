"""Kafka producer/consumer for durable real-time incident feeds."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from backend.config import get_settings
from backend.integrations import live_events

logger = logging.getLogger(__name__)

_producer = None
_consumer_task: asyncio.Task | None = None
_started = False


async def start() -> None:
    """Start Kafka producer and consumer if enabled."""
    global _producer, _consumer_task, _started
    cfg = get_settings()
    if not cfg.kafka_enabled:
        logger.info("Kafka disabled — using in-process SSE only")
        return
    if _started:
        return

    try:
        from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
    except ImportError as exc:
        logger.warning("aiokafka not installed: %s", exc)
        return

    bootstrap = cfg.kafka_bootstrap_servers
    try:
        _producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await _producer.start()
        _consumer_task = asyncio.create_task(_consume_loop(AIOKafkaConsumer), name="kafka-consumer")
        _started = True
        logger.info("Kafka connected at %s", bootstrap)
    except Exception as exc:
        logger.warning("Kafka unavailable at %s — SSE will work without broker: %s", bootstrap, exc)
        if _producer:
            try:
                await _producer.stop()
            except Exception:
                pass
            _producer = None


async def stop() -> None:
    """Stop Kafka client tasks."""
    global _producer, _consumer_task, _started
    if _consumer_task:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
        _consumer_task = None
    if _producer:
        await _producer.stop()
        _producer = None
    _started = False


async def publish(topic: str, payload: dict[str, Any]) -> bool:
    """Publish JSON to Kafka. Returns False if broker unavailable."""
    if _producer is None:
        return False
    try:
        await _producer.send_and_wait(topic, payload)
        return True
    except Exception as exc:
        logger.error("Kafka publish failed: %s", exc)
        return False


async def emit_incident(incident: dict[str, Any]) -> None:
    """Publish incident to Kafka; consumer fans out to SSE. Falls back to direct SSE."""
    cfg = get_settings()
    if cfg.kafka_enabled and _producer:
        ok = await publish(cfg.kafka_incident_topic, {"type": "incident", "incident": incident})
        if ok:
            return
    await live_events.broadcast("incident", {"incident": incident})


async def emit_anomaly(anomaly: dict[str, Any]) -> None:
    cfg = get_settings()
    if cfg.kafka_enabled and _producer:
        ok = await publish(cfg.kafka_anomaly_topic, {"type": "anomaly", "anomaly": anomaly})
        if ok:
            return
    await live_events.broadcast("anomaly", {"anomaly": anomaly})


async def _consume_loop(consumer_cls) -> None:
    """Read Kafka topics and fan-out to SSE subscribers (multi-replica safe)."""
    cfg = get_settings()
    topics = [cfg.kafka_incident_topic, cfg.kafka_anomaly_topic]
    consumer = consumer_cls(
        *topics,
        bootstrap_servers=cfg.kafka_bootstrap_servers,
        group_id=cfg.kafka_consumer_group,
        auto_offset_reset="latest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    await consumer.start()
    logger.info("Kafka consumer subscribed to %s", topics)
    try:
        async for msg in consumer:
            payload = msg.value
            if not isinstance(payload, dict):
                continue
            event_type = payload.get("type")
            if event_type in ("incident", "anomaly"):
                await live_events.broadcast(event_type, payload)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.error("Kafka consumer error: %s", exc, exc_info=True)
    finally:
        await consumer.stop()


def is_connected() -> bool:
    return _producer is not None
