"""
Shared Pydantic request/response models.

All schemas live here — adding a new agent means adding its models here only.
"""
from typing import Optional
from pydantic import BaseModel, Field


# ── Shared ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    ollama_model: str
    environment: str


class IngestResponse(BaseModel):
    status: str
    ingested: dict[str, int]
    duration_seconds: float


# ── Alert Triage ──────────────────────────────────────────────────────────────

class AlertPayload(BaseModel):
    name: str = Field(..., examples=["KubePodCrashLooping"])
    description: str = Field(..., examples=["Pod restarting > 5 times in 10 minutes"])
    labels: dict[str, str] = Field(default_factory=dict)
    value: Optional[float] = None
    environment: str = Field(default="production")
    firing_since: Optional[str] = Field(default=None)


class TriageResponse(BaseModel):
    severity: str
    confidence: float
    reasoning: str
    suggested_fix: str
    similar_incidents: list[str]
    escalate: bool
    estimated_impact: str
    llm_tier: str = "local"
    complexity: str = "low"


# ── Knowledge Chat ────────────────────────────────────────────────────────────

class ChatPayload(BaseModel):
    question: str = Field(..., min_length=1, examples=["How do I recover from a pod CrashLoopBackOff in the iam namespace?"])
    session_id: str = Field(default="default", examples=["user-abc-123"])
    environment: str = Field(default="production")
    agent_mode: str = Field(default="off", examples=["off", "sre", "full"])


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]
    session_id: str
    llm_tier: str
    complexity: str


class ClearSessionResponse(BaseModel):
    session_id: str
    cleared: bool


# ── Runbook Executor ──────────────────────────────────────────────────────────

class RunbookPayload(BaseModel):
    alert_name: str = Field(..., examples=["KubePodCrashLooping"])
    description: str = Field(..., examples=["OOMKilled in ping-identity-auth"])
    environment: str = Field(default="production")
    labels: dict[str, str] = Field(default_factory=dict)


class RunbookStep(BaseModel):
    number: int
    description: str
    command: str
    expected_output: str = ""
    risk_level: str  # SAFE | REQUIRES_APPROVAL | DANGEROUS


class RunbookResponse(BaseModel):
    runbook_source: Optional[str]
    runbook_title: str
    estimated_time: str
    steps: list[RunbookStep]
    safe_steps_count: int
    pending_approval: list[RunbookStep]
    similarity_score: float = 0.0
    llm_tier: str


# ── RCA Generator ─────────────────────────────────────────────────────────────

class TimelineEvent(BaseModel):
    time: str
    event: str
    actor: str = "system"


class RCAPayload(BaseModel):
    title: str = Field(..., examples=["SiteMinder CPU Spike — SSO Outage"])
    severity: str = Field(default="P2", examples=["P1"])
    environment: str = Field(default="production")
    affected_services: list[str] = Field(default_factory=list)
    duration_minutes: int = Field(default=0, ge=0)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    resolution: str = Field(default="", examples=["Rolled back ConfigMap, restarted pods"])


class ActionItem(BaseModel):
    action: str
    owner: str
    priority: str
    due: str


class RCAImpact(BaseModel):
    duration_minutes: int = 0
    users_affected: str = "unknown"
    services_affected: list[str] = Field(default_factory=list)


class RCAResponse(BaseModel):
    title: str
    severity: str
    summary: str
    root_cause: str
    contributing_factors: list[str]
    impact: RCAImpact
    timeline: list[TimelineEvent]
    remediation: str
    prevention: list[str]
    action_items: list[ActionItem]
    detection_gap: str
    rca_markdown: str
    llm_tier: str
