"""
Slack notifier — posts triage results to an incident channel.

Usage:
  post_triage_alert(alert_name, triage_result)

Requires: SLACK_WEBHOOK_URL in .env
If the webhook is empty, calls are silently skipped (safe default).
All errors are logged and swallowed — a Slack failure must never
bring down the triage pipeline.
"""
import logging
from typing import Any

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)

_SEVERITY_EMOJI = {"P1": "🔴", "P2": "🟡", "P3": "🟢"}
_TIER_EMOJI = {"local": "🏠", "standard": "☁️", "advanced": "⚡", "premium": "💎"}


def post_triage_alert(alert_name: str, result: dict[str, Any]) -> bool:
    """
    Post a triage result to Slack. Returns True on success, False otherwise.
    Never raises — caller does not need to handle Slack failures.
    """
    cfg = get_settings()
    if not cfg.slack_webhook_url:
        logger.debug("Slack webhook not configured — skipping notification")
        return False

    severity = result.get("severity", "P2")
    emoji = _SEVERITY_EMOJI.get(severity, "⚠️")
    tier = result.get("llm_tier", "local")
    tier_emoji = _TIER_EMOJI.get(tier, "🤖")
    escalate = result.get("escalate", False)

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} Alert Triage: {alert_name}",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Severity:*\n{severity}"},
                {"type": "mrkdwn", "text": f"*Confidence:*\n{round((result.get('confidence', 0)) * 100)}%"},
                {"type": "mrkdwn", "text": f"*Impact:*\n{result.get('estimated_impact', 'unknown')}"},
                {"type": "mrkdwn", "text": f"*LLM:*\n{tier_emoji} {tier}"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Reasoning:*\n{result.get('reasoning', '')}"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Suggested Fix:*\n```{result.get('suggested_fix', '')}```",
            },
        },
    ]

    if escalate:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "🚨 *Escalation required* — low confidence or P1 severity. Page the on-call engineer.",
            },
        })

    payload = {"blocks": blocks}

    try:
        resp = httpx.post(cfg.slack_webhook_url, json=payload, timeout=5.0)
        resp.raise_for_status()
        logger.info("Slack notification sent for alert '%s' (severity=%s)", alert_name, severity)
        return True
    except httpx.HTTPStatusError as exc:
        logger.error("Slack webhook returned %s: %s", exc.response.status_code, exc.response.text)
    except Exception as exc:
        logger.error("Slack notification failed: %s", exc)
    return False


def post_rca_complete(title: str, result: dict[str, Any]) -> bool:
    """Post an RCA completion notice to Slack."""
    cfg = get_settings()
    if not cfg.slack_webhook_url:
        return False

    severity = result.get("severity", "P2")
    emoji = _SEVERITY_EMOJI.get(severity, "⚠️")
    impact = result.get("impact", {})

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📋 RCA Complete: {title}"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Severity:*\n{emoji} {severity}"},
                {"type": "mrkdwn", "text": f"*Duration:*\n{impact.get('duration_minutes', '?')} min"},
                {"type": "mrkdwn", "text": f"*Users affected:*\n{impact.get('users_affected', 'unknown')}"},
                {"type": "mrkdwn", "text": f"*Detection gap:*\n{result.get('detection_gap', 'unknown')}"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Root Cause:*\n{result.get('root_cause', '')}"},
        },
    ]

    action_items = result.get("action_items", [])
    if action_items:
        items_text = "\n".join(
            f"• [{a.get('priority')}] {a.get('action')} — {a.get('owner')} by {a.get('due')}"
            for a in action_items[:5]
        )
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Action Items:*\n{items_text}"},
        })

    try:
        resp = httpx.post(cfg.slack_webhook_url, json={"blocks": blocks}, timeout=5.0)
        resp.raise_for_status()
        logger.info("Slack RCA notification sent for '%s'", title)
        return True
    except Exception as exc:
        logger.error("Slack RCA notification failed: %s", exc)
    return False
