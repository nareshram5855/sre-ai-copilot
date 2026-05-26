"""Append-only execution audit log (SQLite MVP)."""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.llm.sanitizer import _scrub

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "audit.db"

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS execution_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    execution_id TEXT NOT NULL,
    incident_id TEXT,
    actor TEXT NOT NULL DEFAULT 'system',
    action_type TEXT NOT NULL,
    tool_name TEXT,
    command_details TEXT,
    status TEXT NOT NULL,
    error TEXT,
    approval_required INTEGER NOT NULL DEFAULT 0,
    approved_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_execution_id ON execution_audit(execution_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON execution_audit(timestamp DESC);
"""


@dataclass
class AuditEntry:
    timestamp: str
    execution_id: str
    action_type: str
    status: str
    incident_id: str = ""
    actor: str = "system"
    tool_name: str = ""
    command_details: str = ""
    error: str = ""
    approval_required: bool = False
    approved_by: str = ""


class ExecutionAuditStore:
    def __init__(self, db_path: str | Path = _DEFAULT_DB) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_CREATE_SQL)
        self._conn.commit()
        logger.info("ExecutionAuditStore ready at %s", self._db_path)

    def append(self, entry: AuditEntry) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO execution_audit (
                    timestamp, execution_id, incident_id, actor, action_type,
                    tool_name, command_details, status, error,
                    approval_required, approved_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.timestamp,
                    entry.execution_id,
                    entry.incident_id,
                    entry.actor,
                    entry.action_type,
                    entry.tool_name,
                    entry.command_details,
                    entry.status,
                    entry.error,
                    1 if entry.approval_required else 0,
                    entry.approved_by or None,
                ),
            )
            self._conn.commit()

    def list_entries(
        self,
        *,
        limit: int = 50,
        execution_id: str | None = None,
        action_type: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 500))
        where: list[str] = []
        params: list[Any] = []
        if execution_id:
            where.append("execution_id = ?")
            params.append(execution_id)
        if action_type:
            where.append("action_type = ?")
            params.append(action_type)
        if status:
            where.append("status = ?")
            params.append(status)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        sql = f"SELECT * FROM execution_audit {clause} ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, tuple(params)).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def distinct_action_types(self) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT action_type FROM execution_audit ORDER BY action_type"
            ).fetchall()
        return [r["action_type"] for r in rows]

    def distinct_statuses(self) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT status FROM execution_audit ORDER BY status"
            ).fetchall()
        return [r["status"] for r in rows]

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "timestamp": row["timestamp"],
            "execution_id": row["execution_id"],
            "incident_id": row["incident_id"] or "",
            "actor": row["actor"],
            "action_type": row["action_type"],
            "tool_name": row["tool_name"] or "",
            "command_details": row["command_details"] or "",
            "status": row["status"],
            "error": row["error"] or "",
            "approval_required": bool(row["approval_required"]),
            "approved_by": row["approved_by"] or "",
        }

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def sanitize_details(payload: Any) -> str:
    """Serialize and redact command/args for audit storage."""
    try:
        if isinstance(payload, str):
            text = payload
        else:
            text = json.dumps(payload, default=str)
    except Exception:
        text = str(payload)
    return _scrub(text[:4000])


def log_execution_audit(
    *,
    execution_id: str,
    action_type: str,
    status: str,
    incident_id: str = "",
    actor: str = "system",
    tool_name: str = "",
    command_details: Any = "",
    error: str = "",
    approval_required: bool = False,
    approved_by: str = "",
) -> None:
    store = get_audit_store()
    if store is None:
        return
    try:
        details = sanitize_details(command_details) if command_details else ""
        store.append(
            AuditEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                execution_id=execution_id,
                incident_id=incident_id,
                actor=actor,
                action_type=action_type,
                tool_name=tool_name,
                command_details=details,
                status=status,
                error=_scrub(error)[:1000] if error else "",
                approval_required=approval_required,
                approved_by=approved_by,
            )
        )
    except Exception as exc:
        logger.warning("Failed to write execution audit entry: %s", exc)


_audit_store: ExecutionAuditStore | None = None


def init_audit_store(db_path: str | Path | None = None) -> ExecutionAuditStore:
    global _audit_store
    _audit_store = ExecutionAuditStore(db_path or _DEFAULT_DB)
    return _audit_store


def get_audit_store() -> ExecutionAuditStore | None:
    return _audit_store
