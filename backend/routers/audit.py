"""Execution audit log API."""
from fastapi import APIRouter, Query

from backend.memory.audit_store import get_audit_store

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("/executions")
def list_execution_audit(
    limit: int = Query(default=50, ge=1, le=500),
    execution_id: str | None = Query(default=None),
    action_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> dict:
    """
    Return append-only audit entries for executor actions (newest first).

    Filters:
      * ``execution_id`` — exact match
      * ``action_type`` — execution_start | tool_read | tool_write | approval_required | …
      * ``status`` — started | success | error | denied | approved | pending
    """
    store = get_audit_store()
    if store is None:
        return {"entries": [], "count": 0}
    entries = store.list_entries(
        limit=limit,
        execution_id=execution_id or None,
        action_type=action_type or None,
        status=status or None,
    )
    return {"entries": entries, "count": len(entries)}


@router.get("/facets")
def audit_facets() -> dict:
    """Distinct values for UI filter dropdowns."""
    store = get_audit_store()
    if store is None:
        return {"action_types": [], "statuses": []}
    return {
        "action_types": store.distinct_action_types(),
        "statuses": store.distinct_statuses(),
    }
