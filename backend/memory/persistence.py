"""Central persistence bootstrap — Redis with in-memory fallback."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from backend.config import Settings, get_settings
from backend.memory.checkpointer_factory import create_checkpointer
from backend.memory.dedup_store import (
    AnomalyFingerprintStore,
    InMemoryAnomalyFingerprintStore,
    InMemoryTriageDedupStore,
    RedisAnomalyFingerprintStore,
    RedisTriageDedupStore,
)
from backend.memory.session_store import InMemorySessionStore
from backend.memory.store_proxy import SessionStoreProxy, TriageDedupProxy

logger = logging.getLogger(__name__)

session_store = SessionStoreProxy(InMemorySessionStore())
triage_dedup_store = TriageDedupProxy(InMemoryTriageDedupStore())
anomaly_fingerprint_store: AnomalyFingerprintStore = InMemoryAnomalyFingerprintStore()

_persistence_state: "PersistenceState | None" = None


@dataclass
class PersistenceState:
    redis_available: bool = False
    session_backend: str = "memory"
    checkpointer_backend: str = "memory"
    dedup_backend: str = "memory"
    redis_client: Any | None = None


def get_persistence_state() -> PersistenceState:
    global _persistence_state
    if _persistence_state is None:
        _persistence_state = init_persistence()
    return _persistence_state


def init_persistence(settings: Settings | None = None) -> PersistenceState:
    """Wire session store, dedup stores, and LangGraph checkpointer. Safe to call once at startup."""
    global _persistence_state, anomaly_fingerprint_store

    cfg = settings or get_settings()
    state = PersistenceState()

    redis_client = _connect_redis(cfg) if cfg.redis_enabled else None
    if redis_client is not None:
        state.redis_available = True
        state.redis_client = redis_client

    session_backend, session_impl = _build_session_store(cfg, redis_client)
    session_store.set_delegate(session_impl)
    state.session_backend = session_backend

    dedup_backend, triage_impl, anomaly_impl = _build_dedup_stores(cfg, redis_client)
    triage_dedup_store.set_delegate(triage_impl)
    anomaly_fingerprint_store = anomaly_impl
    state.dedup_backend = dedup_backend

    checkpointer, cp_backend = create_checkpointer(
        redis_enabled=cfg.redis_enabled and state.redis_available,
        redis_host=cfg.redis_host,
        redis_port=cfg.redis_port,
        redis_password=cfg.redis_password,
        sqlite_path=cfg.checkpoint_sqlite_path,
    )
    state.checkpointer_backend = cp_backend
    _init_executor_graph(checkpointer)

    from backend.memory.audit_store import init_audit_store

    if cfg.audit_enabled:
        init_audit_store(cfg.audit_sqlite_path)

    from backend.memory.recruiter_store import init_recruiter_store

    init_recruiter_store(cfg.recruiter_sqlite_path)

    _persistence_state = state
    logger.info(
        "Persistence init: session=%s dedup=%s checkpoints=%s redis=%s",
        state.session_backend,
        state.dedup_backend,
        state.checkpointer_backend,
        state.redis_available,
    )
    return state


def _connect_redis(cfg: Settings) -> Any | None:
    try:
        import redis

        client = redis.Redis(
            host=cfg.redis_host,
            port=cfg.redis_port,
            password=cfg.redis_password or None,
            decode_responses=True,
            socket_connect_timeout=3,
        )
        client.ping()
        logger.info("Redis connected at %s:%d", cfg.redis_host, cfg.redis_port)
        return client
    except Exception as exc:
        logger.warning("Redis unavailable (%s) — using in-memory fallbacks", exc)
        return None


def _build_session_store(cfg: Settings, redis_client: Any | None) -> tuple[str, Any]:
    if redis_client is not None:
        from backend.memory.redis_store import RedisSessionStore

        try:
            store = RedisSessionStore(
                host=cfg.redis_host,
                port=cfg.redis_port,
                password=cfg.redis_password or None,
                ttl_seconds=cfg.redis_session_ttl_seconds,
            )
            return "redis", store
        except Exception as exc:
            logger.warning("RedisSessionStore init failed (%s) — in-memory fallback", exc)
    return "memory", InMemorySessionStore(
        max_sessions=cfg.session_max_count,
        max_history=cfg.session_max_history,
        ttl_seconds=cfg.session_ttl_seconds,
    )


def _build_dedup_stores(
    cfg: Settings,
    redis_client: Any | None,
) -> tuple[str, Any, AnomalyFingerprintStore]:
    if redis_client is not None:
        return (
            "redis",
            RedisTriageDedupStore(redis_client, ttl_seconds=cfg.redis_dedup_ttl_seconds),
            RedisAnomalyFingerprintStore(redis_client, ttl_seconds=cfg.redis_dedup_ttl_seconds),
        )
    return "memory", InMemoryTriageDedupStore(), InMemoryAnomalyFingerprintStore()


def _init_executor_graph(checkpointer: Any) -> None:
    from backend.agents import executor_agent

    executor_agent.init_graph(checkpointer)
