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
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from backend.agents.triage_agent import TriageAgent
from backend.integrations.metrics import record_slack, record_triage
from backend.integrations.slack import post_triage_alert

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/webhook", tags=["alertmanager"])

_agent = TriageAgent()

# Deduplicating store keyed by (alert_name, namespace).
# Preserves insertion order (Python 3.7+), newest entries bubble to top via re-insert.
_recent_triages: dict[tuple[str, str], "RecentTriage"] = {}


def get_fire_count(alert_name: str, namespace: str) -> int:
    """Return how many times this alert has fired (from dedup store)."""
    entry = _recent_triages.get((alert_name, namespace))
    return entry.fire_count if entry else 1


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


@router.get("/alertmanager/recent", response_model=list[RecentTriage])
def recent_triages(limit: int = 10) -> list[RecentTriage]:
    """Return deduplicated auto-triaged alerts, newest first, sorted by severity."""
    _SEV = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}
    items = list(_recent_triages.values())
    items.sort(key=lambda t: (_SEV.get(t.severity, 9), t.triaged_at), reverse=False)
    return items[:limit]


# ── Background task ───────────────────────────────────────────────────────────

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
        key = (alert_name, alert.labels.get("namespace", "unknown"))
        existing = _recent_triages.pop(key, None)
        _recent_triages[key] = RecentTriage(
            alert_name=alert_name,
            severity=severity,
            summary=(result.get("reasoning") or "")[:150],
            suggested_fix=(
                " ".join(result["suggested_fix"])
                if isinstance(result.get("suggested_fix"), list)
                else (result.get("suggested_fix") or "")
            )[:250],
            namespace=alert.labels.get("namespace", "unknown"),
            pod=alert.labels.get("pod", alert.labels.get("instance", "unknown")),
            triaged_at=datetime.now(timezone.utc).isoformat(),
            escalate=escalated,
            llm_tier=tier,
            fire_count=(existing.fire_count + 1) if existing else 1,
        )
        # Cap at 20 unique entries
        if len(_recent_triages) > 20:
            _recent_triages.pop(next(iter(_recent_triages)))

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
