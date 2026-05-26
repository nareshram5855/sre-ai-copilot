"""Recruiter resume page views and feedback (SQLite)."""
from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "recruiter.db"
_UA_SNIPPET_MAX = 120

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS recruiter_stats (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    total_views INTEGER NOT NULL DEFAULT 0,
    unique_views INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO recruiter_stats (id, total_views, unique_views) VALUES (1, 0, 0);

CREATE TABLE IF NOT EXISTS visitors (
    visitor_id TEXT PRIMARY KEY,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    device_class TEXT,
    user_agent_snippet TEXT,
    referrer TEXT,
    country_code TEXT
);
CREATE INDEX IF NOT EXISTS idx_visitors_last_seen
    ON visitors(last_seen DESC);
CREATE INDEX IF NOT EXISTS idx_visitors_first_seen
    ON visitors(first_seen DESC);

CREATE TABLE IF NOT EXISTS recruiter_view_sessions (
    session_id TEXT PRIMARY KEY,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    visitor_id TEXT
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
    is_new_visitor: bool


@dataclass
class RecruiterFeedbackEntry:
    session_id: str = ""
    name: str = ""
    email: str = ""
    feedback: str = ""
    reasons: list[str] | None = None
    rating: int | None = None


def _truncate_id(value: str, n: int = 8) -> str:
    if len(value) <= n:
        return value
    return value[:n] + "…"


def _truncate_text(value: str | None, max_len: int) -> str | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    return text[:max_len] if len(text) > max_len else text


def _sqlite_has_recruiter_data(db_path: Path) -> bool:
    """True if the SQLite file contains non-empty recruiter analytics."""
    if not db_path.is_file() or db_path.stat().st_size == 0:
        return False
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return False
    try:
        try:
            row = conn.execute(
                "SELECT total_views FROM recruiter_stats WHERE id = 1"
            ).fetchone()
            if row and int(row[0]) > 0:
                return True
        except sqlite3.OperationalError:
            return False
        for table in ("visitors", "recruiter_view_sessions", "recruiter_feedback"):
            try:
                cnt = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                if cnt and int(cnt[0]) > 0:
                    return True
            except sqlite3.OperationalError:
                continue
        return False
    finally:
        conn.close()


def maybe_migrate_legacy_recruiter_db(target_path: str | Path) -> bool:
    """Copy legacy backend/data/recruiter.db to target when target is empty.

    Helps local dev (DATA_DIR=/data) and one-time Railway cutover if the old
    ephemeral file still exists on disk. Never overwrites a target that already
    has analytics data.
    """
    target = Path(target_path).resolve()
    legacy = _DEFAULT_DB.resolve()
    if target == legacy:
        return False
    if not legacy.is_file() or not _sqlite_has_recruiter_data(legacy):
        return False
    if target.is_file() and _sqlite_has_recruiter_data(target):
        return False

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(legacy, target)
    logger.info("Migrated recruiter analytics from %s to %s", legacy, target)
    return True


class RecruiterStore:
    def __init__(self, db_path: str | Path = _DEFAULT_DB) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_CREATE_SQL)
        self._migrate_schema()
        self._conn.commit()
        logger.info("RecruiterStore ready at %s", self._db_path)

    def _migrate_schema(self) -> None:
        cols = {
            row[1]
            for row in self._conn.execute(
                "PRAGMA table_info(recruiter_view_sessions)"
            ).fetchall()
        }
        if cols and "visitor_id" not in cols:
            self._conn.execute(
                "ALTER TABLE recruiter_view_sessions ADD COLUMN visitor_id TEXT"
            )

        visitor_cols = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(visitors)").fetchall()
        }
        if visitor_cols and "country_code" not in visitor_cols:
            self._conn.execute(
                "ALTER TABLE visitors ADD COLUMN country_code TEXT"
            )

    def record_view(
        self,
        session_id: str | None = None,
        visitor_id: str | None = None,
        *,
        device_class: str | None = None,
        user_agent_snippet: str | None = None,
        referrer: str | None = None,
        country_code: str | None = None,
    ) -> RecruiterViewResult:
        now = datetime.now(timezone.utc).isoformat()
        sid = (session_id or "").strip()
        vid = (visitor_id or "").strip()
        device = _truncate_text(device_class, 32)
        ua = _truncate_text(user_agent_snippet, _UA_SNIPPET_MAX)
        ref = _truncate_text(referrer, 512)
        country = _truncate_text(country_code, 2)
        if country:
            country = country.upper()

        with self._lock:
            self._conn.execute(
                "UPDATE recruiter_stats SET total_views = total_views + 1 WHERE id = 1"
            )
            is_new_session = False
            is_new_visitor = False

            if vid:
                row = self._conn.execute(
                    "SELECT visitor_id FROM visitors WHERE visitor_id = ?",
                    (vid,),
                ).fetchone()
                if row is None:
                    self._conn.execute(
                        """
                        INSERT INTO visitors (
                            visitor_id, first_seen, last_seen,
                            device_class, user_agent_snippet, referrer,
                            country_code
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (vid, now, now, device, ua, ref, country),
                    )
                    self._conn.execute(
                        "UPDATE recruiter_stats SET unique_views = unique_views + 1 WHERE id = 1"
                    )
                    is_new_visitor = True
                else:
                    self._conn.execute(
                        """
                        UPDATE visitors
                        SET last_seen = ?,
                            device_class = COALESCE(?, device_class),
                            user_agent_snippet = COALESCE(?, user_agent_snippet),
                            referrer = COALESCE(?, referrer),
                            country_code = COALESCE(?, country_code)
                        WHERE visitor_id = ?
                        """,
                        (now, device, ua, ref, country, vid),
                    )
            elif sid:
                row = self._conn.execute(
                    "SELECT session_id FROM recruiter_view_sessions WHERE session_id = ?",
                    (sid,),
                ).fetchone()
                if row is None:
                    self._conn.execute(
                        """
                        INSERT INTO recruiter_view_sessions (session_id, first_seen, last_seen, visitor_id)
                        VALUES (?, ?, ?, NULL)
                        """,
                        (sid, now, now),
                    )
                    self._conn.execute(
                        "UPDATE recruiter_stats SET unique_views = unique_views + 1 WHERE id = 1"
                    )
                    is_new_session = True
                else:
                    self._conn.execute(
                        "UPDATE recruiter_view_sessions SET last_seen = ? WHERE session_id = ?",
                        (now, sid),
                    )

            if sid and vid:
                row = self._conn.execute(
                    "SELECT session_id FROM recruiter_view_sessions WHERE session_id = ?",
                    (sid,),
                ).fetchone()
                if row is None:
                    self._conn.execute(
                        """
                        INSERT INTO recruiter_view_sessions (session_id, first_seen, last_seen, visitor_id)
                        VALUES (?, ?, ?, ?)
                        """,
                        (sid, now, now, vid),
                    )
                    is_new_session = True
                else:
                    self._conn.execute(
                        """
                        UPDATE recruiter_view_sessions
                        SET last_seen = ?, visitor_id = COALESCE(?, visitor_id)
                        WHERE session_id = ?
                        """,
                        (now, vid, sid),
                    )

            self._conn.commit()
            stats = self._conn.execute(
                "SELECT total_views, unique_views FROM recruiter_stats WHERE id = 1"
            ).fetchone()

        return RecruiterViewResult(
            total_views=int(stats["total_views"]),
            unique_views=int(stats["unique_views"]),
            is_new_session=is_new_session,
            is_new_visitor=is_new_visitor,
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
        """Admin-only: views, visitor uniques, daily breakdown, recent visitors."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        with self._lock:
            try:
                stats_row = self._conn.execute(
                    "SELECT total_views, unique_views FROM recruiter_stats WHERE id = 1"
                ).fetchone()

                today_row = self._conn.execute(
                    "SELECT COUNT(*) AS cnt FROM visitors WHERE first_seen LIKE ?",
                    (f"{today}%",),
                ).fetchone()
                if not today_row or int(today_row["cnt"]) == 0:
                    today_row = self._conn.execute(
                        "SELECT COUNT(*) AS cnt FROM recruiter_view_sessions WHERE first_seen LIKE ?",
                        (f"{today}%",),
                    ).fetchone()

                feedback_row = self._conn.execute(
                    "SELECT COUNT(*) AS cnt FROM recruiter_feedback"
                ).fetchone()

                visitor_rows = self._conn.execute(
                    """SELECT visitor_id, device_class, country_code, first_seen, last_seen
                       FROM visitors
                       ORDER BY last_seen DESC LIMIT 20"""
                ).fetchall()

                if not visitor_rows:
                    session_rows = self._conn.execute(
                        """SELECT session_id, first_seen, last_seen, visitor_id
                           FROM recruiter_view_sessions
                           ORDER BY last_seen DESC LIMIT 20"""
                    ).fetchall()
                else:
                    session_rows = []

                daily_rows = self._conn.execute(
                    """SELECT SUBSTR(first_seen, 1, 10) AS day, COUNT(*) AS cnt
                       FROM visitors
                       WHERE first_seen >= date('now', '-6 days')
                       GROUP BY day ORDER BY day DESC"""
                ).fetchall()
                if not daily_rows:
                    daily_rows = self._conn.execute(
                        """SELECT SUBSTR(first_seen, 1, 10) AS day, COUNT(*) AS cnt
                           FROM recruiter_view_sessions
                           WHERE first_seen >= date('now', '-6 days')
                           GROUP BY day ORDER BY day DESC"""
                    ).fetchall()
            except Exception as e:
                logger.error("Error querying recruiter database: %s", str(e), exc_info=True)
                raise

        recent_visitors = [
            {
                "visitor_id": _truncate_id(row["visitor_id"]),
                "device_class": row["device_class"] or "",
                "country_code": row["country_code"] or "",
                "first_seen": row["first_seen"],
                "last_seen": row["last_seen"],
            }
            for row in visitor_rows
            if row
        ]

        if not recent_visitors and session_rows:
            recent_visitors = [
                {
                    "visitor_id": _truncate_id(
                        (row["visitor_id"] or row["session_id"] or "unknown")
                    ),
                    "device_class": "",
                    "country_code": "",
                    "first_seen": row["first_seen"],
                    "last_seen": row["last_seen"],
                }
                for row in session_rows
                if row
            ]

        recent_sessions = [
            {
                "session_id": entry["visitor_id"],
                "visitor_id": entry["visitor_id"],
                "device_class": entry["device_class"],
                "country_code": entry["country_code"],
                "first_seen": entry["first_seen"],
                "last_seen": entry["last_seen"],
            }
            for entry in recent_visitors
        ]

        return {
            "total_views": int(stats_row["total_views"]) if stats_row else 0,
            "unique_views": int(stats_row["unique_views"]) if stats_row else 0,
            "today_views": int(today_row["cnt"]) if today_row else 0,
            "feedback_count": int(feedback_row["cnt"]) if feedback_row else 0,
            "recent_visitors": recent_visitors,
            "recent_sessions": recent_sessions,
            "daily_views": [
                {"day": row["day"], "views": int(row["cnt"])}
                for row in daily_rows
                if row
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
    path = Path(db_path or _DEFAULT_DB)
    from backend.config import get_settings

    cfg = get_settings()
    data_dir = (cfg.data_dir or "").strip()
    if data_dir and path.resolve() == (Path(data_dir) / "recruiter.db").resolve():
        maybe_migrate_legacy_recruiter_db(path)
    _recruiter_store = RecruiterStore(path)
    return _recruiter_store


def get_recruiter_store() -> RecruiterStore | None:
    return _recruiter_store
