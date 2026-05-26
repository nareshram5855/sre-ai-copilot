"""Recruiter resume page views and feedback (SQLite)."""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "recruiter.db"

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS recruiter_stats (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    total_views INTEGER NOT NULL DEFAULT 0,
    unique_views INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO recruiter_stats (id, total_views, unique_views) VALUES (1, 0, 0);

CREATE TABLE IF NOT EXISTS recruiter_view_sessions (
    session_id TEXT PRIMARY KEY,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_recruiter_sessions_last_seen
    ON recruiter_view_sessions(last_seen DESC);

CREATE TABLE IF NOT EXISTS recruiter_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submitted_at TEXT NOT NULL,
    session_id TEXT,
    name TEXT,
    email TEXT,
    feedback TEXT NOT NULL,
    reasons TEXT,
    rating INTEGER
);
CREATE INDEX IF NOT EXISTS idx_recruiter_feedback_submitted
    ON recruiter_feedback(submitted_at DESC);
"""


@dataclass
class RecruiterViewResult:
    total_views: int
    unique_views: int
    is_new_session: bool


@dataclass
class RecruiterFeedbackEntry:
    session_id: str = ""
    name: str = ""
    email: str = ""
    feedback: str = ""
    reasons: list[str] | None = None
    rating: int | None = None


class RecruiterStore:
    def __init__(self, db_path: str | Path = _DEFAULT_DB) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_CREATE_SQL)
        self._conn.commit()
        logger.info("RecruiterStore ready at %s", self._db_path)

    def record_view(self, session_id: str | None = None) -> RecruiterViewResult:
        now = datetime.now(timezone.utc).isoformat()
        sid = (session_id or "").strip()

        with self._lock:
            self._conn.execute(
                "UPDATE recruiter_stats SET total_views = total_views + 1 WHERE id = 1"
            )
            is_new = False
            if sid:
                row = self._conn.execute(
                    "SELECT session_id FROM recruiter_view_sessions WHERE session_id = ?",
                    (sid,),
                ).fetchone()
                if row is None:
                    self._conn.execute(
                        """
                        INSERT INTO recruiter_view_sessions (session_id, first_seen, last_seen)
                        VALUES (?, ?, ?)
                        """,
                        (sid, now, now),
                    )
                    self._conn.execute(
                        "UPDATE recruiter_stats SET unique_views = unique_views + 1 WHERE id = 1"
                    )
                    is_new = True
                else:
                    self._conn.execute(
                        "UPDATE recruiter_view_sessions SET last_seen = ? WHERE session_id = ?",
                        (now, sid),
                    )
            self._conn.commit()
            stats = self._conn.execute(
                "SELECT total_views, unique_views FROM recruiter_stats WHERE id = 1"
            ).fetchone()

        return RecruiterViewResult(
            total_views=int(stats["total_views"]),
            unique_views=int(stats["unique_views"]),
            is_new_session=is_new,
        )

    def get_stats(self) -> dict[str, int]:
        with self._lock:
            row = self._conn.execute(
                "SELECT total_views, unique_views FROM recruiter_stats WHERE id = 1"
            ).fetchone()
        if row is None:
            return {"total_views": 0, "unique_views": 0}
        return {
            "total_views": int(row["total_views"]),
            "unique_views": int(row["unique_views"]),
        }

    def get_detailed_stats(self) -> dict[str, Any]:
        """Admin-only: returns rich analytics — views, unique visitors, daily breakdown, recent sessions."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

        with self._lock:
            try:
                logger.info("Querying recruiter stats from database at %s", self._db_path)
                stats_row = self._conn.execute(
                    "SELECT total_views, unique_views FROM recruiter_stats WHERE id = 1"
                ).fetchone()
                logger.info("Stats row: %s", stats_row)

                today_row = self._conn.execute(
                    "SELECT COUNT(*) AS cnt FROM recruiter_view_sessions WHERE first_seen LIKE ?",
                    (f"{today}%",),
                ).fetchone()
                logger.info("Today row: %s", today_row)

                feedback_row = self._conn.execute(
                    "SELECT COUNT(*) AS cnt FROM recruiter_feedback"
                ).fetchone()
                logger.info("Feedback row: %s", feedback_row)

                recent_rows = self._conn.execute(
                    """SELECT session_id, first_seen, last_seen
                       FROM recruiter_view_sessions
                       ORDER BY last_seen DESC LIMIT 20"""
                ).fetchall()
                logger.info("Recent rows count: %s", len(recent_rows) if recent_rows else 0)

                # Views by day for last 7 days
                daily_rows = self._conn.execute(
                    """SELECT SUBSTR(first_seen, 1, 10) AS day, COUNT(*) AS cnt
                       FROM recruiter_view_sessions
                       WHERE first_seen >= date('now', '-6 days')
                       GROUP BY day ORDER BY day DESC"""
                ).fetchall()
                logger.info("Daily rows count: %s", len(daily_rows) if daily_rows else 0)
            except Exception as e:
                logger.error("Error querying recruiter database: %s", str(e), exc_info=True)
                raise

        return {
            "total_views": int(stats_row["total_views"]) if stats_row else 0,
            "unique_views": int(stats_row["unique_views"]) if stats_row else 0,
            "today_views": int(today_row["cnt"]) if today_row else 0,
            "feedback_count": int(feedback_row["cnt"]) if feedback_row else 0,
            "recent_sessions": [
                {
                    "session_id": (row["session_id"][:8] + "…") if row["session_id"] else "unknown",
                    "first_seen": row["first_seen"],
                    "last_seen": row["last_seen"],
                }
                for row in recent_rows if row
            ],
            "daily_views": [
                {"day": row["day"], "views": int(row["cnt"])}
                for row in daily_rows if row
            ],
        }

    def submit_feedback(self, entry: RecruiterFeedbackEntry) -> int:
        now = datetime.now(timezone.utc).isoformat()
        reasons_json = json.dumps(entry.reasons or [])
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO recruiter_feedback (
                    submitted_at, session_id, name, email, feedback, reasons, rating
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    entry.session_id or None,
                    entry.name or None,
                    entry.email or None,
                    entry.feedback.strip(),
                    reasons_json,
                    entry.rating,
                ),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def list_feedback(self, *, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 200))
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, submitted_at, session_id, name, email, feedback, reasons, rating
                FROM recruiter_feedback
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._feedback_row_to_dict(row) for row in rows]

    @staticmethod
    def _feedback_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        reasons_raw = row["reasons"] or "[]"
        try:
            reasons = json.loads(reasons_raw)
        except json.JSONDecodeError:
            reasons = []
        return {
            "id": row["id"],
            "submitted_at": row["submitted_at"],
            "session_id": row["session_id"] or "",
            "name": row["name"] or "",
            "email": row["email"] or "",
            "feedback": row["feedback"],
            "reasons": reasons if isinstance(reasons, list) else [],
            "rating": row["rating"],
        }

    def close(self) -> None:
        with self._lock:
            self._conn.close()


_recruiter_store: RecruiterStore | None = None


def init_recruiter_store(db_path: str | Path | None = None) -> RecruiterStore:
    global _recruiter_store
    _recruiter_store = RecruiterStore(db_path or _DEFAULT_DB)
    return _recruiter_store


def get_recruiter_store() -> RecruiterStore | None:
    return _recruiter_store
