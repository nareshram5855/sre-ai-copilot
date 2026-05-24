"""
Redis-backed session store — drop-in replacement for InMemorySessionStore.

Why Redis over InMemory for production:
- Survives pod restarts (stateless backend pods)
- Works across multiple replicas (horizontal scaling)
- Built-in TTL via EXPIRE — no manual eviction loop needed
- Compatible with existing ChatAgent interface (get_history / add_exchange)

Local fallback: if Redis is unreachable, the store raises ConnectionError at
init time. Routers should fall back to InMemorySessionStore in that case.
Use get_session_store() factory in main.py instead of importing directly.

Session key schema:
  sre:session:<session_id>  →  Redis list of serialized LangChain messages
  TTL: 4 hours (configurable via REDIS_SESSION_TTL_SECONDS)
"""
import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

logger = logging.getLogger(__name__)

_MSG_TYPE_MAP = {"human": HumanMessage, "ai": AIMessage}
_SESSION_PREFIX = "sre:session:"
_DEFAULT_TTL = 4 * 3600  # 4 hours
_MAX_HISTORY = 20  # messages per session (10 exchanges)


def _serialize(msg: BaseMessage) -> str:
    return json.dumps({"type": msg.type, "content": msg.content})


def _deserialize(raw: str) -> BaseMessage:
    data = json.loads(raw)
    cls = _MSG_TYPE_MAP.get(data["type"], HumanMessage)
    return cls(content=data["content"])


class RedisSessionStore:
    """
    Redis-backed session store with the same interface as InMemorySessionStore.
    Requires: pip install redis
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        ttl_seconds: int = _DEFAULT_TTL,
    ) -> None:
        import redis  # lazy import — not in requirements unless Phase 3 is active

        self._ttl = ttl_seconds
        self._r = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password or None,
            decode_responses=True,
            socket_connect_timeout=3,
        )
        # Verify connectivity at startup — fail fast rather than silent degradation
        self._r.ping()
        logger.info("RedisSessionStore connected to %s:%d", host, port)

    def _key(self, session_id: str) -> str:
        return f"{_SESSION_PREFIX}{session_id}"

    def get_history(self, session_id: str) -> list[BaseMessage]:
        try:
            raw_list = self._r.lrange(self._key(session_id), 0, -1)
            return [_deserialize(r) for r in raw_list]
        except Exception as exc:
            logger.error("Redis get_history failed for session=%s: %s", session_id, exc)
            return []

    def add_exchange(self, session_id: str, question: str, answer: str) -> None:
        try:
            key = self._key(session_id)
            pipe = self._r.pipeline()
            pipe.rpush(key, _serialize(HumanMessage(content=question)))
            pipe.rpush(key, _serialize(AIMessage(content=answer)))
            # Cap history to _MAX_HISTORY messages (trim oldest)
            pipe.ltrim(key, -_MAX_HISTORY, -1)
            pipe.expire(key, self._ttl)
            pipe.execute()
        except Exception as exc:
            logger.error("Redis add_exchange failed for session=%s: %s", session_id, exc)

    def clear(self, session_id: str) -> bool:
        try:
            return bool(self._r.delete(self._key(session_id)))
        except Exception as exc:
            logger.error("Redis clear failed for session=%s: %s", session_id, exc)
            return False

    def session_count(self) -> int:
        try:
            return len(self._r.keys(f"{_SESSION_PREFIX}*"))
        except Exception:
            return -1

    def health_check(self) -> bool:
        try:
            self._r.ping()
            return True
        except Exception:
            return False
