"""LangGraph checkpointer factory — Redis → SQLite → in-memory fallback."""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_SQLITE = Path(__file__).resolve().parent.parent / "data" / "checkpoints.db"


def create_checkpointer(
    *,
    redis_enabled: bool = False,
    redis_host: str = "localhost",
    redis_port: int = 6379,
    redis_password: str = "",
    sqlite_path: str | Path = _DEFAULT_SQLITE,
) -> tuple[Any, str]:
    """
    Return (checkpointer, backend_name).
    Tries RedisSaver when redis_enabled, then SqliteSaver, then MemorySaver.
    """
    if redis_enabled:
        saver = _try_redis_checkpointer(redis_host, redis_port, redis_password)
        if saver is not None:
            return saver, "redis"

    saver = _try_sqlite_checkpointer(sqlite_path)
    if saver is not None:
        return saver, "sqlite"

    from langgraph.checkpoint.memory import MemorySaver

    logger.info("Using in-memory LangGraph checkpointer (no persistence)")
    return MemorySaver(), "memory"


def _try_redis_checkpointer(host: str, port: int, password: str) -> Any | None:
    try:
        from langgraph.checkpoint.redis import RedisSaver
    except ImportError:
        logger.info("langgraph-checkpoint-redis not installed — skipping Redis checkpointer")
        return None

    auth = f":{password}@" if password else ""
    conn = f"redis://{auth}{host}:{port}"
    try:
        saver = RedisSaver.from_conn_string(conn)
        saver.setup()
        logger.info("LangGraph RedisSaver connected to %s:%d", host, port)
        return saver
    except Exception as exc:
        logger.warning("Redis checkpointer unavailable (%s) — falling back", exc)
        return None


def _try_sqlite_checkpointer(path: str | Path) -> Any | None:
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
    except ImportError:
        logger.info("langgraph-checkpoint-sqlite not installed — skipping SQLite checkpointer")
        return None

    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        saver = SqliteSaver(conn)
        logger.info("LangGraph SqliteSaver using %s", db_path)
        return saver
    except Exception as exc:
        logger.warning("SQLite checkpointer unavailable (%s) — falling back", exc)
        return None
