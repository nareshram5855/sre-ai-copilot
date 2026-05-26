"""Unit tests for privacy-safe country resolution from request headers."""
from starlette.requests import Request

from backend.utils.client_geo import country_from_request


def _request(headers: dict[str, str] | None = None) -> Request:
    raw = [
        (k.lower().encode("latin-1"), v.encode("latin-1"))
        for k, v in (headers or {}).items()
    ]
    scope = {"type": "http", "headers": raw, "method": "POST", "path": "/"}
    return Request(scope)


def test_country_from_cf_ipcountry():
    req = _request({"CF-IPCountry": "us"})
    assert country_from_request(req) == "US"


def test_country_from_cf_ipcountry_ignores_xx():
    req = _request({"CF-IPCountry": "XX"})
    assert country_from_request(req) is None


def test_country_from_request_no_header():
    assert country_from_request(_request()) is None
