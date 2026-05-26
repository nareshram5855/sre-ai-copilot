"""Unit tests for background anomaly watcher."""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from backend.integrations import anomaly_watcher
from backend.memory.dedup_store import InMemoryAnomalyFingerprintStore
from backend.memory import persistence


@pytest.fixture(autouse=True)
def reset_state():
    persistence.anomaly_fingerprint_store = InMemoryAnomalyFingerprintStore()
    anomaly_watcher.reset_fingerprints()
    yield
    persistence.anomaly_fingerprint_store = InMemoryAnomalyFingerprintStore()
    anomaly_watcher.reset_fingerprints()


def test_fingerprint_detects_new_anomaly():
    a = {"service": "auth-service", "type": "HIGH_ERROR_RATE", "severity": "critical", "label": "1.5/s"}
    fp = anomaly_watcher._fingerprint([a])
    assert anomaly_watcher._anomaly_key(a) in fp
    assert fp - frozenset() == fp


@pytest.mark.asyncio
async def test_poll_loop_emits_new_anomalies(monkeypatch):
    watch_result = {
        "overall_health": "critical",
        "anomaly_count": 1,
        "anomalies": [
            {
                "service": "auth-service",
                "type": "HIGH_ERROR_RATE",
                "severity": "critical",
                "label": "1.5000 errors/s",
            }
        ],
    }
    emit = AsyncMock()
    monkeypatch.setattr("backend.integrations.anomaly_watcher.emit_anomaly", emit)

    calls = 0

    async def fake_sleep(_seconds):
        nonlocal calls
        calls += 1
        if calls >= 2:
            raise asyncio.CancelledError()

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    with patch("backend.routers.observability.watch_summary", return_value=watch_result):
        with pytest.raises(asyncio.CancelledError):
            await anomaly_watcher._poll_loop()

    emit.assert_awaited_once()
    payload = emit.await_args.args[0]
    assert payload["service"] == "auth-service"
    assert payload["anomaly_count"] == 1


@pytest.mark.asyncio
async def test_poll_loop_skips_unchanged_anomalies(monkeypatch):
    existing = {
        "service": "auth-service",
        "type": "HIGH_ERROR_RATE",
        "severity": "critical",
        "label": "1.5000 errors/s",
    }
    persistence.anomaly_fingerprint_store.set_fingerprints(anomaly_watcher._fingerprint([existing]))
    watch_result = {
        "overall_health": "critical",
        "anomaly_count": 1,
        "anomalies": [existing],
    }
    emit = AsyncMock()
    monkeypatch.setattr("backend.integrations.anomaly_watcher.emit_anomaly", emit)

    async def fake_sleep(_seconds):
        raise asyncio.CancelledError()

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    with patch("backend.routers.observability.watch_summary", return_value=watch_result):
        with pytest.raises(asyncio.CancelledError):
            await anomaly_watcher._poll_loop()

    emit.assert_not_awaited()
