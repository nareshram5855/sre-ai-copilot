"""Privacy-safe coarse geo from request headers (no IP storage)."""
from __future__ import annotations

from starlette.requests import Request


def country_from_request(request: Request) -> str | None:
    """Resolve ISO 3166-1 alpha-2 country from trusted edge headers only."""
    cf = request.headers.get("CF-IPCountry")
    if cf:
        code = cf.strip().upper()
        if len(code) == 2 and code.isalpha() and code != "XX":
            return code
    return None
