"""Deduplication stores for anomaly fingerprints and AlertManager triage cache."""
from __future__ import annotations

import json
import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)

_ANOMALY_FP_KEY = "sre:anomaly:fingerprints"
_TRIAGE_PREFIX = "sre:triage:"
_TRIAGE_INDEX = "sre:triage:index"
_MAX_TRIAGES = 20
_DEFAULT_ANOMALY_TTL = 24 * 3600


class AnomalyFingerprintStore(Protocol):
    def get_fingerprints(self) -> frozenset[str]: ...
    def set_fingerprints(self, fingerprints: frozenset[str]) -> None: ...
    def reset(self) -> None: ...


class InMemoryAnomalyFingerprintStore:
    def __init__(self) -> None:
        self._fingerprints: frozenset[str] = frozenset()

    def get_fingerprints(self) -> frozenset[str]:
        return self._fingerprints

    def set_fingerprints(self, fingerprints: frozenset[str]) -> None:
        self._fingerprints = fingerprints

    def reset(self) -> None:
        self._fingerprints = frozenset()


class RedisAnomalyFingerprintStore:
    def __init__(self, redis_client: Any, ttl_seconds: int = _DEFAULT_ANOMALY_TTL) -> None:
        self._r = redis_client
        self._ttl = ttl_seconds

    def get_fingerprints(self) -> frozenset[str]:
        try:
            members = self._r.smembers(_ANOMALY_FP_KEY)
            return frozenset(members or [])
        except Exception as exc:
            logger.warning("Redis anomaly fingerprint read failed: %s", exc)
            return frozenset()

    def set_fingerprints(self, fingerprints: frozenset[str]) -> None:
        try:
            pipe = self._r.pipeline()
            pipe.delete(_ANOMALY_FP_KEY)
            if fingerprints:
                pipe.sadd(_ANOMALY_FP_KEY, *sorted(fingerprints))
            pipe.expire(_ANOMALY_FP_KEY, self._ttl)
            pipe.execute()
        except Exception as exc:
            logger.warning("Redis anomaly fingerprint write failed: %s", exc)

    def reset(self) -> None:
        try:
            self._r.delete(_ANOMALY_FP_KEY)
        except Exception as exc:
            logger.warning("Redis anomaly fingerprint reset failed: %s", exc)


class InMemoryTriageDedupStore:
    """Insertion-ordered dedup cache keyed by (alert_name, namespace)."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], Any] = {}

    def upsert(self, key: tuple[str, str], entry: Any) -> None:
        self._store.pop(key, None)
        self._store[key] = entry
        while len(self._store) > _MAX_TRIAGES:
            self._store.pop(next(iter(self._store)))

    def get(self, key: tuple[str, str]) -> Any | None:
        return self._store.get(key)

    def list_recent(self, limit: int = 10) -> list[Any]:
        return list(self._store.values())[:limit]

    def get_fire_count(self, alert_name: str, namespace: str) -> int:
        entry = self._store.get((alert_name, namespace))
        return entry.fire_count if entry else 1


class RedisTriageDedupStore:
    def __init__(self, redis_client: Any, ttl_seconds: int = 24 * 3600) -> None:
        self._r = redis_client
        self._ttl = ttl_seconds

    def _field(self, key: tuple[str, str]) -> str:
        alert_name, namespace = key
        return f"{alert_name}:{namespace}"

    def _triage_key(self, field: str) -> str:
        return f"{_TRIAGE_PREFIX}{field}"

    def upsert(self, key: tuple[str, str], entry: Any) -> None:
        field = self._field(key)
        try:
            payload = entry.model_dump() if hasattr(entry, "model_dump") else dict(entry)
            score = payload.get("triaged_at", "")
            pipe = self._r.pipeline()
            pipe.set(self._triage_key(field), json.dumps(payload), ex=self._ttl)
            pipe.zadd(_TRIAGE_INDEX, {field: self._score(score)})
            pipe.zremrangebyrank(_TRIAGE_INDEX, 0, -(_MAX_TRIAGES + 1))
            pipe.execute()
        except Exception as exc:
            logger.warning("Redis triage upsert failed for %s: %s", key, exc)

    def get(self, key: tuple[str, str]) -> Any | None:
        from backend.routers.alertmanager import RecentTriage

        try:
            raw = self._r.get(self._triage_key(self._field(key)))
            if not raw:
                return None
            return RecentTriage(**json.loads(raw))
        except Exception as exc:
            logger.warning("Redis triage get failed for %s: %s", key, exc)
            return None

    def list_recent(self, limit: int = 10) -> list[Any]:
        from backend.routers.alertmanager import RecentTriage

        try:
            fields = self._r.zrevrange(_TRIAGE_INDEX, 0, max(limit - 1, 0))
            items: list[Any] = []
            for field in fields:
                raw = self._r.get(self._triage_key(field))
                if raw:
                    items.append(RecentTriage(**json.loads(raw)))
            return items
        except Exception as exc:
            logger.warning("Redis triage list failed: %s", exc)
            return []

    def get_fire_count(self, alert_name: str, namespace: str) -> int:
        entry = self.get((alert_name, namespace))
        return entry.fire_count if entry else 1

    @staticmethod
    def _score(triaged_at: str) -> float:
        if not triaged_at:
            return 0.0
        try:
            from datetime import datetime

            dt = datetime.fromisoformat(triaged_at.replace("Z", "+00:00"))
            return dt.timestamp()
        except Exception:
            return 0.0
