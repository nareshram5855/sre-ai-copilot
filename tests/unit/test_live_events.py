"""Unit tests for in-process SSE fan-out (live_events)."""
import asyncio
import json

import pytest

from backend.integrations import live_events


@pytest.mark.asyncio
async def test_broadcast_reaches_subscriber():
    async def collect_one():
        async for chunk in live_events.subscribe("incidents"):
            data = json.loads(chunk.removeprefix("data: ").strip())
            if data.get("type") == "heartbeat":
                continue
            return chunk

    task = asyncio.create_task(collect_one())
    await asyncio.sleep(0.05)
    await live_events.broadcast("incident", {"incident": {"alert_name": "HighCPU"}})
    chunk = await asyncio.wait_for(task, timeout=2.0)
    assert "HighCPU" in chunk
    assert "incident" in chunk


@pytest.mark.asyncio
async def test_anomaly_broadcast_reaches_anomaly_stream_only():
    async def collect_one():
        async for chunk in live_events.subscribe("anomalies"):
            data = json.loads(chunk.removeprefix("data: ").strip())
            if data.get("type") == "heartbeat":
                continue
            return chunk

    task = asyncio.create_task(collect_one())
    await asyncio.sleep(0.05)
    await live_events.broadcast("anomaly", {"anomaly": {"service": "auth-service", "type": "HIGH_ERROR_RATE"}})
    chunk = await asyncio.wait_for(task, timeout=2.0)
    assert "auth-service" in chunk
    assert "anomaly" in chunk


@pytest.mark.asyncio
async def test_incident_not_delivered_to_anomaly_stream():
    received = []

    async def drain():
        async for chunk in live_events.subscribe("anomalies"):
            data = json.loads(chunk.removeprefix("data: ").strip())
            if data.get("type") != "heartbeat":
                received.append(data)

    task = asyncio.create_task(drain())
    await asyncio.sleep(0.05)
    await live_events.broadcast("incident", {"incident": {"alert_name": "HighCPU"}})
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert received == []


@pytest.mark.asyncio
async def test_subscriber_count_tracks_connections():
    before = live_events.subscriber_count("incidents")

    async def drain():
        async for _ in live_events.subscribe("incidents"):
            pass

    task = asyncio.create_task(drain())
    await asyncio.sleep(0.05)
    assert live_events.subscriber_count("incidents") == before + 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0.05)
    assert live_events.subscriber_count("incidents") == before


@pytest.mark.asyncio
async def test_emit_anomaly_falls_back_to_sse_when_kafka_disabled(monkeypatch):
    from backend.config import Settings
    from backend.integrations import kafka_bus

    monkeypatch.setattr(
        "backend.integrations.kafka_bus.get_settings",
        lambda: Settings(kafka_enabled=False),
    )

    async def collect_one():
        async for chunk in live_events.subscribe("anomalies"):
            data = json.loads(chunk.removeprefix("data: ").strip())
            if data.get("type") == "heartbeat":
                continue
            return data

    task = asyncio.create_task(collect_one())
    await asyncio.sleep(0.05)
    await kafka_bus.emit_anomaly({"service": "order-service", "type": "HIGH_LATENCY", "severity": "critical"})
    data = await asyncio.wait_for(task, timeout=2.0)
    assert data["type"] == "anomaly"
    assert data["anomaly"]["service"] == "order-service"


@pytest.mark.asyncio
async def test_kafka_bus_start_noop_when_disabled(monkeypatch):
    """Kafka start should exit cleanly when KAFKA_ENABLED=false."""
    from backend.config import Settings
    from backend.integrations import kafka_bus

    monkeypatch.setattr(
        "backend.integrations.kafka_bus.get_settings",
        lambda: Settings(kafka_enabled=False),
    )
    await kafka_bus.start()
    assert kafka_bus.is_connected() is False
