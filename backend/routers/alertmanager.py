"""
AlertManager webhook receiver.

AlertManager fires POST /api/v1/webhook/alertmanager when an alert fires.
This router auto-triages each alert and (optionally) posts to Slack.

AlertManager configuration (alertmanager.yml):
  receivers:
    - name: sre-ai-copilot
      webhook_configs:
        - url: http://sre-ai-backend:8080/api/v1/webhook/alertmanager
          send_resolved: false

AlertManager payload shape (subset we use):
  {
    "alerts": [
      {
        "status": "firing",
        "labels": {"alertname": "KubePodCrashLooping", "severity": "warning", ...},
        "annotations": {"summary": "...", "description": "..."},
        "startsAt": "2024-01-15T10:02:00Z"
      }
    ]
  }
"""
import logging
import asyncio
import threading
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Query
from pydantic import BaseModel, Field

from backend.agents.triage_agent import TriageAgent
from backend.integrations import pagerduty, servicenow
from backend.integrations.kafka_bus import emit_incident
from backend.integrations.metrics import record_slack, record_triage
from backend.integrations.slack import post_triage_alert
from backend.memory.persistence import triage_dedup_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/webhook", tags=["alertmanager"])

_agent = TriageAgent()

# Deduplicating store keyed by (alert_name, namespace) — Redis or in-memory.
_recent_triages = triage_dedup_store


def get_fire_count(alert_name: str, namespace: str) -> int:
    """Return how many times this alert has fired (from dedup store)."""
    return triage_dedup_store.get_fire_count(alert_name, namespace)


def get_recent_triage(alert_name: str, namespace: str):
    """Return the most recent triage entry for (alert_name, namespace) if present."""
    return triage_dedup_store.get((alert_name, namespace))


# ── Pydantic models for AlertManager payload ──────────────────────────────────

class AMAlert(BaseModel):
    status: str = "firing"
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    startsAt: str = ""
    endsAt: str = ""
    fingerprint: str = ""


class AMPayload(BaseModel):
    version: str = "4"
    groupKey: str = ""
    status: str = "firing"
    receiver: str = ""
    alerts: list[AMAlert] = Field(default_factory=list)


class WebhookResponse(BaseModel):
    received: int
    processed: int
    skipped: int


class RecentTriage(BaseModel):
    alert_name: str
    severity: str
    summary: str
    suggested_fix: str
    namespace: str
    pod: str
    triaged_at: str
    escalate: bool
    llm_tier: str
    fire_count: int = 1
    servicenow_number: str = ""
    pagerduty_triggered: bool = False


# ── Route ─────────────────────────────────────────────────────────────────────

@router.post("/alertmanager", response_model=WebhookResponse, status_code=202)
async def receive_alertmanager(
    payload: AMPayload,
    background_tasks: BackgroundTasks,
) -> WebhookResponse:
    """
    Receive AlertManager webhook, triage firing alerts in the background.
    Returns 202 immediately so AlertManager doesn't time out waiting for LLM.
    """
    firing = [a for a in payload.alerts if a.status == "firing"]
    if not firing:
        return WebhookResponse(received=len(payload.alerts), processed=0, skipped=len(payload.alerts))

    for alert in firing:
        background_tasks.add_task(_triage_alert, alert)

    logger.info(
        "AlertManager webhook: %d alerts received, %d firing → queued for triage",
        len(payload.alerts), len(firing),
    )
    return WebhookResponse(
        received=len(payload.alerts),
        processed=len(firing),
        skipped=len(payload.alerts) - len(firing),
    )


# Namespaces that belong on the SRE Command Center incident strip (not kube-system noise).
_FLEET_NAMESPACES = frozenset({"synthetic", "observability", "kafka", "sre-ai"})


@router.get("/alertmanager/recent", response_model=list[RecentTriage])
def recent_triages(
    limit: int = 10,
    scope: str = Query("all", pattern="^(all|fleet|relevant|synthetic)$"),
) -> list[RecentTriage]:
    """Return deduplicated auto-triaged alerts, newest first, sorted by severity."""
    _SEV = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}
    fetch_limit = limit * 5 if scope in ("fleet", "relevant", "synthetic") else limit
    items = triage_dedup_store.list_recent(limit=fetch_limit)
    if scope in ("fleet", "relevant", "synthetic"):
        items = [
            t for t in items
            if t.namespace in _FLEET_NAMESPACES
            or (t.alert_name or "").startswith("Synthetic")
        ]
    items.sort(key=lambda t: (_SEV.get(t.severity, 9), t.triaged_at), reverse=False)
    return items[:limit]


# ── Background task ───────────────────────────────────────────────────────────

def _schedule_emit(incident: dict[str, Any]) -> None:
    """Fire-and-forget async emit from sync background task thread."""

    def _run() -> None:
        try:
            asyncio.run(emit_incident(incident))
        except Exception as exc:
            logger.warning("Failed to emit incident event: %s", exc)

    threading.Thread(target=_run, daemon=True, name="incident-emit").start()


def _triage_alert(alert: AMAlert) -> None:
    alert_name = alert.labels.get("alertname", "UnknownAlert")
    try:
        payload = _build_triage_payload(alert)
        result = _agent.execute(payload)

        severity = result.get("severity", "P2")
        tier = result.get("llm_tier", "local")
        escalated = result.get("escalate", False)
        record_triage(severity=severity, tier=tier, escalated=escalated)

        slack_ok = post_triage_alert(alert_name, result)
        record_slack("triage", slack_ok)

        # Upsert into deduplication store — same alert+namespace updates in place
        namespace = alert.labels.get("namespace", "unknown")
        key = (alert_name, namespace)
        existing = triage_dedup_store.get(key)
        summary_text = (result.get("reasoning") or "")[:150]
        suggested_fix = (
            " ".join(result["suggested_fix"])
            if isinstance(result.get("suggested_fix"), list)
            else (result.get("suggested_fix") or "")
        )[:250]

        # ── Side-effects on first fire only (avoid duplicate INC/page) ───
        snow_number = existing.servicenow_number if existing else ""
        pd_triggered = existing.pagerduty_triggered if existing else False
        if not existing and severity in ("P1", "P2"):
            try:
                created = servicenow.create_incident(
                    alert_name=alert_name,
                    namespace=namespace,
                    severity=severity,
                    summary=summary_text,
                    suggested_fix=suggested_fix,
                    extra={"llm_tier": tier},
                )
                snow_number = created or ""
            except Exception as exc:
                logger.warning("ServiceNow auto-create failed: %s", exc)
        if severity == "P1" and not pd_triggered:
            try:
                pd_triggered = pagerduty.trigger(
                    dedup_key=pagerduty.dedup_key_for(alert_name, namespace),
                    summary=f"[{severity}] {alert_name} in {namespace}",
                    severity=severity,
                    custom_details={
                        "summary": summary_text,
                        "suggested_fix": suggested_fix,
                        "pod": alert.labels.get("pod", ""),
                    },
                )
            except Exception as exc:
                logger.warning("PagerDuty auto-trigger failed: %s", exc)

        entry = RecentTriage(
            alert_name=alert_name,
            severity=severity,
            summary=summary_text,
            suggested_fix=suggested_fix,
            namespace=namespace,
            pod=alert.labels.get("pod", alert.labels.get("instance", "unknown")),
            triaged_at=datetime.now(timezone.utc).isoformat(),
            escalate=escalated,
            llm_tier=tier,
            fire_count=(existing.fire_count + 1) if existing else 1,
            servicenow_number=snow_number,
            pagerduty_triggered=pd_triggered,
        )
        triage_dedup_store.upsert(key, entry)
        _schedule_emit(entry.model_dump())

        logger.info(
            "Auto-triage '%s' → %s (confidence=%.2f, escalate=%s, slack=%s)",
            alert_name, severity, result.get("confidence", 0), escalated, slack_ok,
        )
    except Exception as exc:
        logger.error("Auto-triage failed for alert '%s': %s", alert_name, exc, exc_info=True)


def _build_triage_payload(alert: AMAlert) -> dict[str, Any]:
    description = (
        alert.annotations.get("description")
        or alert.annotations.get("summary")
        or f"Alert {alert.labels.get('alertname', '')} firing"
    )
    return {
        "name": alert.labels.get("alertname", "UnknownAlert"),
        "description": description,
        "labels": dict(alert.labels),
        "environment": alert.labels.get("env", alert.labels.get("environment", "production")),
        "firing_since": alert.startsAt or datetime.utcnow().isoformat(),
    }
