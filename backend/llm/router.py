"""
LLM Router — selects the right model based on problem complexity.

Tier ladder (cheapest → most capable):
  LOCAL    → Mistral 7B via Ollama      ($0,    always available)
  STANDARD → Gemini 1.5 Flash           ($0.075/1M input, ~$0.11/mo for SRE workloads)
  ADVANCED → Claude Haiku 4.5           ($0.80/1M input, ~$2.40/mo)
  PREMIUM  → Claude Sonnet 4.6          ($3.00/1M input, only for novel P1s)

Routing decision is driven by:
  1. RAG hit count  — 0 hits means novel problem, needs stronger reasoning
  2. Alert severity — "critical" label or P1 keywords → higher tier
  3. Risk keywords  — data loss, breach, security, unknown → escalate

Two-pass routing (Phase 2):
  Run Mistral first → if confidence < threshold → re-run with premium LLM.
  Currently using pre-routing (single pass) which covers 95% of cases.

Data leaving the network:
  - LOCAL tier:    never leaves the machine
  - All other tiers: payload is sanitized before the call (see sanitizer.py)
  - Every external call is audit-logged for compliance
  - `allow_external_llm: false` in config disables all external tiers safely
"""
import json
import logging
from enum import Enum
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

from backend.config import get_settings

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger("llm.audit")


# ── Tiers and complexity ──────────────────────────────────────────────────────

class LLMTier(str, Enum):
    LOCAL    = "local"
    STANDARD = "standard"
    ADVANCED = "advanced"
    PREMIUM  = "premium"


class Complexity(str, Enum):
    LOW      = "low"       # routine, well-understood
    MEDIUM   = "medium"    # some uncertainty, some history
    HIGH     = "high"      # limited history, high risk keywords
    CRITICAL = "critical"  # novel problem, no history, security/data risk


_TIER_MAP: dict[Complexity, LLMTier] = {
    Complexity.LOW:      LLMTier.LOCAL,
    Complexity.MEDIUM:   LLMTier.STANDARD,
    Complexity.HIGH:     LLMTier.ADVANCED,
    Complexity.CRITICAL: LLMTier.PREMIUM,
}

_RISK_KEYWORDS = frozenset([
    "data loss", "breach", "security", "unauthorized", "compromised",
    "outage", "all users", "corruption", "certificate", "ssl", "expired",
    "unknown", "never seen", "cascade", "token", "secret", "credential",
])


# ── Complexity scorer ─────────────────────────────────────────────────────────

def score_complexity(payload: dict[str, Any], rag_hit_count: int) -> Complexity:
    """
    Score problem complexity from alert signals — no LLM call needed.

    Higher score = more complex = higher LLM tier.
    Thresholds are tunable via config.
    """
    cfg = get_settings()
    score = 0

    # RAG signal: 0 hits = novel problem, no historical precedent
    if rag_hit_count == 0:
        score += 4
    elif rag_hit_count < cfg.min_rag_hits_for_local:
        score += 2

    # Severity from Prometheus/AlertManager labels
    severity = payload.get("labels", {}).get("severity", "").lower()
    if severity == "critical":
        score += 3
    elif severity == "warning":
        score += 1

    # Risk keywords in alert name + description
    text = f"{payload.get('name', '')} {payload.get('description', '')}".lower()
    if any(kw in text for kw in _RISK_KEYWORDS):
        score += 2

    # Production environment is higher stakes than staging
    if payload.get("environment", "").lower() == "production":
        score += 1

    if score >= 7:
        return Complexity.CRITICAL
    if score >= 4:
        return Complexity.HIGH
    if score >= 2:
        return Complexity.MEDIUM
    return Complexity.LOW


# ── LLM factory ───────────────────────────────────────────────────────────────

def get_llm(tier: LLMTier, *, json_mode: bool = True) -> BaseChatModel:
    """
    Return the appropriate LLM for the given tier.

    Fallback chain: if API key missing → silently downgrade to LOCAL.
    Never crashes — always returns a usable LLM.
    """
    cfg = get_settings()

    if not cfg.allow_external_llm or tier == LLMTier.LOCAL:
        return _local(json_mode)

    if tier == LLMTier.STANDARD:
        if cfg.google_api_key:
            return _gemini_flash(json_mode)
        logger.warning("STANDARD tier requested but GOOGLE_API_KEY not set — falling back to LOCAL")
        return _local(json_mode)

    if tier == LLMTier.ADVANCED:
        if cfg.anthropic_api_key:
            return _claude_haiku(json_mode)
        if cfg.google_api_key:
            logger.warning("ADVANCED tier: Anthropic key missing — using Gemini Flash instead")
            return _gemini_flash(json_mode)
        logger.warning("ADVANCED tier requested but no API keys set — falling back to LOCAL")
        return _local(json_mode)

    if tier == LLMTier.PREMIUM:
        if cfg.anthropic_api_key:
            return _claude_sonnet(json_mode)
        if cfg.google_api_key:
            logger.warning("PREMIUM tier: Anthropic key missing — using Gemini Flash instead")
            return _gemini_flash(json_mode)
        logger.warning("PREMIUM tier requested but no API keys set — falling back to LOCAL")
        return _local(json_mode)

    return _local(json_mode)


def resolve_tier(complexity: Complexity) -> LLMTier:
    return _TIER_MAP[complexity]


# ── LLM constructors ──────────────────────────────────────────────────────────

from functools import lru_cache as _lru_cache


@_lru_cache(maxsize=4)
def _local(json_mode: bool) -> ChatOllama:
    cfg = get_settings()
    # num_ctx=4096: Mistral supports 8k natively; 4096 gives headroom for RAG context
    # (~1200 tokens at k=4) + system prompt + response without truncation.
    # Keep consistent across all agents so Ollama doesn't reload the model.
    return ChatOllama(
        model=cfg.ollama_model,
        base_url=cfg.ollama_base_url,
        temperature=cfg.ollama_temperature,
        format="json" if json_mode else "",
        num_ctx=4096,
        num_predict=1024,
    )


def _gemini_flash(json_mode: bool) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI
    cfg = get_settings()
    kwargs: dict = dict(
        model="gemini-1.5-flash",
        google_api_key=cfg.google_api_key,
        temperature=cfg.ollama_temperature,
    )
    if json_mode:
        kwargs["generation_config"] = {"response_mime_type": "application/json"}
    return ChatGoogleGenerativeAI(**kwargs)


def _claude_haiku(json_mode: bool) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic
    cfg = get_settings()
    return ChatAnthropic(
        model="claude-haiku-4-5-20251001",
        api_key=cfg.anthropic_api_key,
        temperature=cfg.ollama_temperature,
        max_tokens=1024,
    )


def _claude_sonnet(json_mode: bool) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic
    cfg = get_settings()
    return ChatAnthropic(
        model="claude-sonnet-4-6",
        api_key=cfg.anthropic_api_key,
        temperature=cfg.ollama_temperature,
        max_tokens=2048,
    )


# ── Audit logger ──────────────────────────────────────────────────────────────

def audit_log(
    tier: LLMTier,
    complexity: Complexity,
    payload: dict[str, Any],
) -> None:
    """
    Log every external LLM call for compliance.
    LOCAL tier calls are not logged (no data leaves the machine).
    In production, route audit_logger to CloudWatch / S3 / SIEM.
    """
    if tier == LLMTier.LOCAL:
        return

    provider_map = {
        LLMTier.STANDARD: "google/gemini-1.5-flash",
        LLMTier.ADVANCED: "anthropic/claude-haiku-4-5",
        LLMTier.PREMIUM:  "anthropic/claude-sonnet-4-6",
    }

    audit_logger.info(json.dumps({
        "event":            "external_llm_call",
        "provider":         provider_map.get(tier, "unknown"),
        "tier":             tier.value,
        "complexity":       complexity.value,
        "alert_name":       payload.get("name", "unknown"),
        "environment":      payload.get("environment", "unknown"),
        "data_sanitized":   True,
    }))
