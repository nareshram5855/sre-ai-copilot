"""
In-memory session store for conversation history.

Thread-safe, TTL-aware, bounded by max_sessions to prevent memory leaks.
In Phase 3 this will be swapped for a Redis-backed store — same interface,
just a different constructor call in the router.
"""
import time
import threading
from dataclasses import dataclass, field
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage


@dataclass
class _Session:
    messages: list[BaseMessage] = field(default_factory=list)
    last_accessed: float = field(default_factory=time.monotonic)


class InMemorySessionStore:

    def __init__(self, max_sessions: int = 500, max_history: int = 20, ttl_seconds: int = 3600):
        self._store: dict[str, _Session] = {}
        self._lock = threading.Lock()
        self._max_sessions = max_sessions
        self._max_history = max_history
        self._ttl = ttl_seconds

    def get_history(self, session_id: str) -> list[BaseMessage]:
        with self._lock:
            session = self._store.get(session_id)
            if not session:
                return []
            session.last_accessed = time.monotonic()
            return list(session.messages)

    def add_exchange(self, session_id: str, question: str, answer: str) -> None:
        with self._lock:
            self._evict_if_needed()
            if session_id not in self._store:
                self._store[session_id] = _Session()
            session = self._store[session_id]
            session.messages.append(HumanMessage(content=question))
            session.messages.append(AIMessage(content=answer))
            if len(session.messages) > self._max_history * 2:
                session.messages = session.messages[-(self._max_history * 2):]
            session.last_accessed = time.monotonic()

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._store.pop(session_id, None)

    def session_count(self) -> int:
        with self._lock:
            return len(self._store)

    def _evict_if_needed(self) -> None:
        now = time.monotonic()
        expired = [sid for sid, s in self._store.items() if now - s.last_accessed > self._ttl]
        for sid in expired:
            del self._store[sid]
        if len(self._store) >= self._max_sessions:
            oldest = min(self._store, key=lambda sid: self._store[sid].last_accessed)
            del self._store[oldest]


# Module-level singleton — shared across all requests in a worker process
session_store = InMemorySessionStore()
