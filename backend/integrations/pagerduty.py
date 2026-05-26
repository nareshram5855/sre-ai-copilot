"""
PagerDuty Events API v2 integration.

Wired by:
  - alertmanager router (P1 triage auto-page)
  - incidents.resolve endpoint (resolve event)
  - ExecutionDrawer "Reject — Escalate" → POST /escalate

Graceful no-op when PAGERDUTY_ROUTING_KEY is empty.
Spec: https://developer.pagerduty.com/docs/events-api-v2/overview
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)

_EVENTS_URL = "https://events.pagerduty.com/v2/enqueue"

# Severity → PagerDuty severity mapping (info | warning | error | critical)
_SEV_MAP = {"P1": "critical", "P2": "error", "P3": "warning", "P4": "info"}


def is_configured() -> bool:
    return bool(get_settings().pagerduty_routing_key)


def trigger(
    *,
    dedup_key: str,
    summary: str,
    severity: str = "P2",
    source: str = "sre-ai-copilot",
    component: str = "",
    group: str = "",
    custom_details: dict[str, Any] | None = None,
) -> bool:
    """
    Fire a `trigger` event. Returns True on success.
    Uses dedup_key for incident deduplication on the PD side.
    """
    return _enqueue(
        action="trigger",
        dedup_key=dedup_key,
        payload={
            "summary": summary[:1024],
            "severity": _SEV_MAP.get(severity, "error"),
            "source": source,
            "component": component or source,
            "group": group or "kubernetes",
            "custom_details": custom_details or {},
        },
    )


def resolve(*, dedup_key: str, summary: str = "") -> bool:
    """Resolve an open PagerDuty incident."""
    return _enqueue(
        action="resolve",
        dedup_key=dedup_key,
        payload={"summary": summary[:512] or "Resolved by SRE AI Copilot"} if summary else None,
    )


def acknowledge(*, dedup_key: str) -> bool:
    return _enqueue(action="acknowledge", dedup_key=dedup_key, payload=None)


def _enqueue(*, action: str, dedup_key: str, payload: dict | None) -> bool:
    cfg = get_settings()
    if not cfg.pagerduty_routing_key:
        logger.debug("PagerDuty routing key not configured — skipping %s", action)
        return False

    body: dict[str, Any] = {
        "routing_key": cfg.pagerduty_routing_key,
        "event_action": action,
        "dedup_key": dedup_key,
    }
    if payload:
        body["payload"] = payload

    try:
        resp = httpx.post(_EVENTS_URL, json=body, timeout=6.0)
        resp.raise_for_status()
        logger.info("PagerDuty %s ok for dedup_key=%s", action, dedup_key)
        return True
    except httpx.HTTPStatusError as exc:
        logger.warning("PagerDuty %s HTTP %s: %s", action, exc.response.status_code, exc.response.text[:200])
    except Exception as exc:
        logger.warning("PagerDuty %s failed: %s", action, exc)
    return False


def dedup_key_for(alert_name: str, namespace: str) -> str:
    """Stable dedup key so triggers + resolves reference the same PD incident."""
    return f"sre-ai:{alert_name}:{namespace or 'unknown'}"
