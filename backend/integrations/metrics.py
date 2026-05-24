"""
Custom Prometheus metrics for SRE AI Copilot.

These supplement the auto-instrumented HTTP metrics from
prometheus_fastapi_instrumentator (request count, latency by route).

Usage:
  from backend.integrations.metrics import TRIAGE_COUNTER, record_agent_run
  TRIAGE_COUNTER.labels(severity="P2", tier="local").inc()
  record_agent_run("triage", tier="local", complexity="medium", duration=1.23)

Scrape endpoint: GET /metrics  (exposed by prometheus_fastapi_instrumentator)
"""
from prometheus_client import Counter, Histogram, Gauge

# ── Triage ────────────────────────────────────────────────────────────────────

TRIAGE_COUNTER = Counter(
    "sre_triage_total",
    "Total alert triage requests",
    ["severity", "tier", "escalated"],
)

# ── Agent execution ───────────────────────────────────────────────────────────

AGENT_DURATION = Histogram(
    "sre_agent_duration_seconds",
    "Agent execution duration",
    ["agent", "tier", "complexity"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

AGENT_ERROR_COUNTER = Counter(
    "sre_agent_errors_total",
    "Total agent failures (fell back to default response)",
    ["agent"],
)

# ── LLM routing ───────────────────────────────────────────────────────────────

LLM_TIER_COUNTER = Counter(
    "sre_llm_tier_total",
    "LLM tier selections",
    ["tier", "complexity"],
)

# ── RAG ───────────────────────────────────────────────────────────────────────

RAG_HIT_HISTOGRAM = Histogram(
    "sre_rag_hits",
    "Number of RAG documents retrieved per query",
    ["collection"],
    buckets=[0, 1, 2, 3, 5, 8],
)

# ── Session store ─────────────────────────────────────────────────────────────

ACTIVE_SESSIONS = Gauge(
    "sre_active_sessions",
    "Current number of active chat sessions",
)

# ── Slack ─────────────────────────────────────────────────────────────────────

SLACK_NOTIFICATION_COUNTER = Counter(
    "sre_slack_notifications_total",
    "Slack notifications sent",
    ["type", "success"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def record_agent_run(
    agent: str,
    tier: str,
    complexity: str,
    duration: float,
    error: bool = False,
) -> None:
    AGENT_DURATION.labels(agent=agent, tier=tier, complexity=complexity).observe(duration)
    LLM_TIER_COUNTER.labels(tier=tier, complexity=complexity).inc()
    if error:
        AGENT_ERROR_COUNTER.labels(agent=agent).inc()


def record_triage(severity: str, tier: str, escalated: bool) -> None:
    TRIAGE_COUNTER.labels(
        severity=severity,
        tier=tier,
        escalated=str(escalated).lower(),
    ).inc()


def record_slack(notification_type: str, success: bool) -> None:
    SLACK_NOTIFICATION_COUNTER.labels(
        type=notification_type,
        success=str(success).lower(),
    ).inc()
