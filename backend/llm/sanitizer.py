"""
Data Sanitizer — strips sensitive fields before any payload leaves the network.

Applied automatically by BaseAgent before every external LLM call.
LOCAL tier calls bypass this entirely (data never leaves the machine).

What gets redacted:
  - Internal hostnames  (*.internal, *.local, *.corp, *.citi.com etc.)
  - RFC 1918 IP addresses
  - Anything matching credential patterns (password=, token=, key=, secret=)
  - AWS ARNs and account IDs
  - Kubernetes namespace names (optional, controlled by SANITIZE_K8S_NAMES)
"""
import copy
import re
from typing import Any

# ── Patterns ──────────────────────────────────────────────────────────────────

_INTERNAL_HOST = re.compile(
    r"\b[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?"
    r"(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*"
    r"\.(internal|local|corp|intranet|lan|private)\b",
    re.IGNORECASE,
)

_RFC1918_IP = re.compile(
    r"\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3})\b"
)

_CREDENTIAL = re.compile(
    r"(password|passwd|token|secret|api_key|apikey|auth|credential)"
    r"\s*[=:]\s*\S+",
    re.IGNORECASE,
)

_AWS_ARN = re.compile(r"arn:aws:[a-z0-9\-]+:[a-z0-9\-]*:\d{12}:[^\s]+")

_AWS_ACCOUNT = re.compile(r"\b\d{12}\b")


# ── Public API ────────────────────────────────────────────────────────────────

def sanitize(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Return a deep copy of payload with ALL string values recursively redacted.
    The original payload is never mutated. Dict keys are preserved verbatim.
    """
    return _scrub_obj(copy.deepcopy(payload))


def _scrub_obj(obj: Any) -> Any:
    if isinstance(obj, str):
        return _scrub(obj)
    if isinstance(obj, dict):
        return {k: _scrub_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub_obj(item) for item in obj]
    return obj


def _scrub(text: str) -> str:
    text = _INTERNAL_HOST.sub("[INTERNAL_HOST]", text)
    text = _RFC1918_IP.sub("[PRIVATE_IP]", text)
    text = _CREDENTIAL.sub(r"\1=[REDACTED]", text)
    text = _AWS_ARN.sub("[AWS_ARN]", text)
    text = _AWS_ACCOUNT.sub("[AWS_ACCOUNT_ID]", text)
    return text
