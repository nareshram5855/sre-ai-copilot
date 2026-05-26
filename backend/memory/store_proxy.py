"""Proxy wrappers so module-level singletons pick up Redis backends after startup."""
from __future__ import annotations

from typing import Any, Protocol


class SessionStoreProtocol(Protocol):
    def get_history(self, session_id: str) -> list: ...
    def add_exchange(self, session_id: str, question: str, answer: str) -> None: ...
    def clear(self, session_id: str) -> None: ...
    def session_count(self) -> int: ...


class SessionStoreProxy:
    """Delegates to the active session store (in-memory or Redis)."""

    def __init__(self, delegate: SessionStoreProtocol) -> None:
        self._delegate = delegate

    def set_delegate(self, delegate: SessionStoreProtocol) -> None:
        self._delegate = delegate

    def get_history(self, session_id: str) -> list:
        return self._delegate.get_history(session_id)

    def add_exchange(self, session_id: str, question: str, answer: str) -> None:
        self._delegate.add_exchange(session_id, question, answer)

    def clear(self, session_id: str) -> None:
        self._delegate.clear(session_id)

    def session_count(self) -> int:
        return self._delegate.session_count()


class TriageDedupProtocol(Protocol):
    def upsert(self, key: tuple[str, str], entry: Any) -> None: ...
    def get(self, key: tuple[str, str]) -> Any | None: ...
    def list_recent(self, limit: int = 10) -> list[Any]: ...
    def get_fire_count(self, alert_name: str, namespace: str) -> int: ...


class TriageDedupProxy:
    def __init__(self, delegate: TriageDedupProtocol) -> None:
        self._delegate = delegate

    def set_delegate(self, delegate: TriageDedupProtocol) -> None:
        self._delegate = delegate

    def upsert(self, key: tuple[str, str], entry: Any) -> None:
        self._delegate.upsert(key, entry)

    def get(self, key: tuple[str, str]) -> Any | None:
        return self._delegate.get(key)

    def list_recent(self, limit: int = 10) -> list[Any]:
        return self._delegate.list_recent(limit)

    def get_fire_count(self, alert_name: str, namespace: str) -> int:
        return self._delegate.get_fire_count(alert_name, namespace)
