"""
Learning Agent — writes successful resolutions back into the knowledge base.

On successful ExecutorAgent runs, embeds the resolution path into the
`resolved_incidents` ChromaDB collection so future triage and executor runs
can retrieve proven fixes faster.

After PROMOTION_THRESHOLD consecutive successes for the same alert type,
auto-promotes the resolution to a runbook markdown file.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.agents.base import BaseAgent
from backend.config import settings
from backend.rag.ingestor import ingest_directory, ingest_text
from backend.rag.retriever import retrieve_with_score

logger = logging.getLogger(__name__)

PROMOTION_THRESHOLD = 3
AUTO_RUNBOOK_DIR = Path(__file__).parent.parent / "knowledge" / "runbooks" / "auto"


class LearningAgent(BaseAgent):
    """Ingest successful incident resolutions into ChromaDB for future RAG retrieval."""

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        alert_name = payload.get("alert_name", "").strip()
        namespace = payload.get("namespace", "").strip()
        outcome = payload.get("outcome", "resolved")
        scratchpad = payload.get("scratchpad") or []
        final_summary = payload.get("final_summary", "")
        triage_summary = payload.get("triage_summary", "")
        fire_count = int(payload.get("fire_count", 1))
        duration_seconds = float(payload.get("time_to_resolve_seconds", 0))

        if not alert_name:
            raise ValueError("alert_name is required")
        if outcome != "resolved":
            return {
                "ingested": False,
                "reason": f"Outcome '{outcome}' is not eligible for learning",
            }

        resolution_steps = self._extract_steps(scratchpad)
        if not resolution_steps and not final_summary:
            return {
                "ingested": False,
                "reason": "No resolution steps or summary to learn from",
            }

        doc_text = self._build_document(
            alert_name=alert_name,
            namespace=namespace,
            final_summary=final_summary,
            triage_summary=triage_summary,
            resolution_steps=resolution_steps,
            fire_count=fire_count,
            duration_seconds=duration_seconds,
        )

        collection = settings.knowledge_collections["resolved_incidents"]
        doc_id = f"{alert_name}:{namespace}:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
        metadata = {
            "source": f"learning/{alert_name}_{namespace}.md",
            "alert_name": alert_name,
            "namespace": namespace,
            "outcome": outcome,
            "fire_count": fire_count,
            "time_to_resolve_seconds": duration_seconds,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "doc_id": doc_id,
        }

        stored = ingest_text(collection, doc_text, metadata, doc_id=doc_id)
        if not stored:
            return {"ingested": False, "reason": "ChromaDB ingest failed"}

        prior_count = self._count_prior_resolutions(alert_name, namespace)
        promoted = False
        if prior_count + 1 >= PROMOTION_THRESHOLD:
            promoted = self._maybe_promote_runbook(
                alert_name=alert_name,
                namespace=namespace,
                resolution_steps=resolution_steps,
                final_summary=final_summary,
            )

        self.logger.info(
            "Learned resolution for %s/%s (prior=%d, promoted=%s)",
            alert_name, namespace, prior_count, promoted,
        )

        return {
            "ingested": True,
            "doc_id": doc_id,
            "collection": collection,
            "prior_resolution_count": prior_count,
            "promoted_to_runbook": promoted,
        }

    def ingest_from_execution(self, snapshot: dict[str, Any], *, fire_count: int = 1) -> dict[str, Any]:
        """Convenience wrapper for ExecutorAgent completion hooks."""
        if snapshot.get("status") != "resolved":
            return {"ingested": False, "reason": f"Status is {snapshot.get('status')}"}

        duration = 0.0
        scratchpad = snapshot.get("scratchpad") or []
        if scratchpad:
            duration = float(len(scratchpad))  # rough proxy when wall-clock unavailable

        payload = {
            "alert_name": snapshot.get("alert_name", ""),
            "namespace": snapshot.get("namespace", ""),
            "outcome": "resolved",
            "scratchpad": scratchpad,
            "final_summary": snapshot.get("final_summary", ""),
            "triage_summary": snapshot.get("triage_summary", ""),
            "fire_count": fire_count,
            "time_to_resolve_seconds": duration,
        }
        return self.execute(payload)

    @staticmethod
    def _extract_steps(scratchpad: list[dict]) -> list[str]:
        steps = []
        for entry in scratchpad:
            action = entry.get("action", "")
            args = entry.get("args") or {}
            observation = (entry.get("observation") or "").strip()
            if not action:
                continue
            arg_str = " ".join(f"{k}={v}" for k, v in args.items() if v)
            line = f"{action} {arg_str}".strip()
            if observation and "error" not in observation.lower()[:40]:
                steps.append(line)
        return steps

    @staticmethod
    def _build_document(
        *,
        alert_name: str,
        namespace: str,
        final_summary: str,
        triage_summary: str,
        resolution_steps: list[str],
        fire_count: int,
        duration_seconds: float,
    ) -> str:
        steps_md = "\n".join(f"{i + 1}. `{step}`" for i, step in enumerate(resolution_steps))
        return f"""# Resolved: {alert_name}

**Namespace:** {namespace}
**Outcome:** alert_cleared
**Fire count at resolution:** {fire_count}
**Time to resolve (approx):** {duration_seconds:.0f}s
**Resolved at:** {datetime.now(timezone.utc).isoformat()}

## Summary
{final_summary or triage_summary or "Auto-resolved by ExecutorAgent."}

## Resolution Steps
{steps_md or "1. See executor scratchpad for details."}

## Alert Context
{triage_summary or "N/A"}
"""

    def _count_prior_resolutions(self, alert_name: str, namespace: str) -> int:
        collection = settings.knowledge_collections["resolved_incidents"]
        query = f"{alert_name} {namespace} resolution"
        try:
            hits = retrieve_with_score(query, collection, k=10)
        except Exception:
            return 0
        count = 0
        for doc, _distance in hits:
            meta = doc.metadata or {}
            if meta.get("alert_name") == alert_name and meta.get("namespace") == namespace:
                count += 1
        return count

    def count_prior_resolutions(self, alert_name: str, namespace: str) -> int:
        """Public accessor used by /incidents/{id}/resolve and frontend hint."""
        if not alert_name:
            return 0
        return self._count_prior_resolutions(alert_name, namespace)

    def _maybe_promote_runbook(
        self,
        *,
        alert_name: str,
        namespace: str,
        resolution_steps: list[str],
        final_summary: str,
    ) -> bool:
        """Write auto-runbook markdown and re-ingest runbooks collection."""
        AUTO_RUNBOOK_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = alert_name.lower().replace(" ", "_")
        path = AUTO_RUNBOOK_DIR / f"{safe_name}.md"

        if path.exists():
            return False

        steps_md = "\n".join(
            f"### Step {i + 1}\n```bash\n{step}\n```"
            for i, step in enumerate(resolution_steps)
        ) or "### Step 1\nReview executor scratchpad for commands."

        content = f"""# Auto-runbook: {alert_name}

> Auto-generated after {PROMOTION_THRESHOLD} successful resolutions.
> Namespace: `{namespace}`

## When to use
Alert `{alert_name}` fires in namespace `{namespace}`.

## Summary
{final_summary or "Proven fix from past auto-resolutions."}

## Steps
{steps_md}

## Rollback
Revert the last kubectl patch or rollout restart if symptoms worsen.
"""
        path.write_text(content, encoding="utf-8")
        logger.info("Promoted auto-runbook: %s", path)

        runbooks_collection = settings.knowledge_collections["runbooks"]
        ingest_directory(runbooks_collection, "runbooks")
        return True

    @staticmethod
    def get_best_resolution(alert_name: str, namespace: str) -> tuple[float, str]:
        """
        Return (similarity, snippet) for the best matching prior resolution.
        Used by ExecutorAgent confidence gating.
        """
        collection = settings.knowledge_collections["resolved_incidents"]
        query = f"{alert_name} {namespace} resolution steps"
        hits = retrieve_with_score(query, collection, k=3)
        best_sim, best_snippet = 0.0, ""
        for doc, distance in hits:
            meta = doc.metadata or {}
            if meta.get("alert_name") != alert_name:
                continue
            similarity = max(0.0, 1.0 - distance)
            if similarity > best_sim:
                best_sim = similarity
                best_snippet = doc.page_content[:300]
        return best_sim, best_snippet


learning_agent = LearningAgent()
