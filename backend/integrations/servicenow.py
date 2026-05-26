"""
ServiceNow integration — auto-create INC tickets from P1/P2 triage,
attach RCA markdown on resolve.

Graceful no-op when SERVICENOW_URL is empty (returns False/None, never raises).
Auth: HTTP Basic with username + password.
Tested against the standard /api/now/table/incident endpoint.

Typical .env:
  SERVICENOW_URL=https://devXXXXX.service-now.com
  SERVICENOW_USER=admin
  SERVICENOW_PASSWORD=<token>
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)

# Severity → ServiceNow impact/urgency mapping
_SEVERITY_TO_IMPACT = {"P1": 1, "P2": 2, "P3": 3, "P4": 3}
_SEVERITY_TO_URGENCY = {"P1": 1, "P2": 2, "P3": 3, "P4": 3}


def is_configured() -> bool:
    cfg = get_settings()
    return bool(cfg.servicenow_url and cfg.servicenow_user and cfg.servicenow_password)


def create_incident(
    *,
    alert_name: str,
    namespace: str,
    severity: str,
    summary: str,
    suggested_fix: str = "",
    extra: dict[str, Any] | None = None,
) -> str | None:
    """
    Create a ServiceNow incident. Returns INC number (e.g. ``INC0010023``) or
    ``None`` when ServiceNow is not configured / call fails.
    """
    if not is_configured():
        logger.debug("ServiceNow not configured — skipping create_incident")
        return None

    cfg = get_settings()
    body = {
        "short_description": f"[{severity}] {alert_name} in {namespace or 'unknown'}",
        "description": _format_description(alert_name, namespace, summary, suggested_fix, extra),
        "impact": _SEVERITY_TO_IMPACT.get(severity, 3),
        "urgency": _SEVERITY_TO_URGENCY.get(severity, 3),
        "category": "infrastructure",
        "subcategory": "kubernetes",
        "caller_id": cfg.servicenow_user,
    }
    try:
        resp = httpx.post(
            f"{cfg.servicenow_url.rstrip('/')}/api/now/table/incident",
            json=body,
            auth=(cfg.servicenow_user, cfg.servicenow_password),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=8.0,
        )
        resp.raise_for_status()
        number = resp.json().get("result", {}).get("number")
        logger.info("ServiceNow INC created: %s for alert=%s", number, alert_name)
        return number
    except httpx.HTTPStatusError as exc:
        logger.warning("ServiceNow create_incident HTTP %s: %s", exc.response.status_code, exc.response.text[:200])
    except Exception as exc:
        logger.warning("ServiceNow create_incident failed: %s", exc)
    return None


def attach_rca(
    *,
    incident_number: str,
    rca_markdown: str,
    final_summary: str = "",
) -> bool:
    """
    Append RCA markdown as a work-note + close the incident.
    Returns True on success. Never raises.
    """
    if not is_configured() or not incident_number:
        return False

    cfg = get_settings()
    # First, lookup sys_id for the incident
    sys_id = _lookup_sys_id(incident_number)
    if not sys_id:
        return False

    body = {
        "work_notes": (final_summary + "\n\n" if final_summary else "") + rca_markdown[:6000],
        "state": "6",        # Resolved
        "close_code": "Solved (Permanently)",
        "close_notes": (final_summary or rca_markdown[:500]),
    }
    try:
        resp = httpx.put(
            f"{cfg.servicenow_url.rstrip('/')}/api/now/table/incident/{sys_id}",
            json=body,
            auth=(cfg.servicenow_user, cfg.servicenow_password),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=8.0,
        )
        resp.raise_for_status()
        logger.info("ServiceNow INC %s closed with RCA attached", incident_number)
        return True
    except Exception as exc:
        logger.warning("ServiceNow attach_rca failed: %s", exc)
        return False


# ── helpers ───────────────────────────────────────────────────────────────────

def _format_description(
    alert_name: str,
    namespace: str,
    summary: str,
    suggested_fix: str,
    extra: dict[str, Any] | None,
) -> str:
    lines = [
        f"Alert: {alert_name}",
        f"Namespace: {namespace or 'unknown'}",
        "",
        "AI Triage Summary:",
        summary or "(no summary)",
    ]
    if suggested_fix:
        lines += ["", "Suggested Fix:", suggested_fix]
    if extra:
        lines += ["", "Context:"]
        for k, v in extra.items():
            lines.append(f"  {k}: {v}")
    lines += ["", "— auto-created by SRE AI Copilot"]
    return "\n".join(lines)


def _lookup_sys_id(incident_number: str) -> str | None:
    cfg = get_settings()
    try:
        resp = httpx.get(
            f"{cfg.servicenow_url.rstrip('/')}/api/now/table/incident",
            params={"sysparm_query": f"number={incident_number}", "sysparm_limit": "1"},
            auth=(cfg.servicenow_user, cfg.servicenow_password),
            headers={"Accept": "application/json"},
            timeout=6.0,
        )
        resp.raise_for_status()
        results = resp.json().get("result", [])
        return results[0].get("sys_id") if results else None
    except Exception as exc:
        logger.warning("ServiceNow sys_id lookup failed: %s", exc)
        return None
