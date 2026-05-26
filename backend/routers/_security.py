"""
API key auth — MVP gate around write endpoints (execute / approve / resolve / escalate).

Behaviour:
  * When ``API_KEY`` env var is **unset / empty**, auth is bypassed (dev mode)
    and a warning is logged on import.
  * When ``API_KEY`` is set, callers must send one of:
        Authorization: Bearer <API_KEY>
        X-API-Key: <API_KEY>
        ?api_key=<API_KEY>
    otherwise the dependency raises HTTP 401.

Use as a FastAPI dependency:

    from backend.routers._security import require_api_key

    @router.post(\"/sensitive\", dependencies=[Depends(require_api_key)])
    def sensitive(): ...

This is intentionally NOT full OIDC — a roadmap doc lives in
``ARCHITECTURE.md`` under \"Auth & RBAC\".
"""
from __future__ import annotations

import logging
import os
import secrets

from fastapi import Header, HTTPException, Query, status

logger = logging.getLogger(__name__)

_LOGGED_BYPASS = False


def _expected_key() -> str:
    """Re-read on every request so tests can mutate os.environ at runtime."""
    return os.getenv("API_KEY", "").strip()


def _warn_bypass_once() -> None:
    global _LOGGED_BYPASS
    if _LOGGED_BYPASS:
        return
    _LOGGED_BYPASS = True
    logger.warning(
        "API_KEY env var is not set — write endpoints are UNAUTHENTICATED "
        "(dev mode). Set API_KEY=<token> in production."
    )


def require_api_key(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    api_key: str | None = Query(default=None),
) -> None:
    """FastAPI dependency — raises 401 unless the request carries a valid key."""
    expected = _expected_key()
    if not expected:
        _warn_bypass_once()
        return  # dev bypass

    presented = None
    if authorization and authorization.lower().startswith("bearer "):
        presented = authorization[7:].strip()
    elif x_api_key:
        presented = x_api_key.strip()
    elif api_key:
        presented = api_key.strip()

    if not presented or not secrets.compare_digest(presented, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key. Send Authorization: Bearer <key> or X-API-Key header.",
            headers={"WWW-Authenticate": "Bearer"},
        )
