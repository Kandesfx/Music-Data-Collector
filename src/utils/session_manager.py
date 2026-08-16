import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Set
from contextlib import contextmanager

from config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SessionManager:
    """Provides local SQLite persistence for track downloads and session recovery."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.SESSION_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    @contextmanager
    def _get_connection(self):
        """Context manager to ensure connection is properly closed and committed."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_tables(self):
        """Create sessions and checkpoint log tables if they do not exist."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    status TEXT DEFAULT 'running',
                    total_tracks INTEGER DEFAULT 0,
                    completed INTEGER DEFAULT 0,
                    failed INTEGER DEFAULT 0,
                    last_track_id TEXT,
                    ended_at TEXT
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS download_checkpoints (
                    spotify_id TEXT PRIMARY KEY,
                    session_id INTEGER,
                    status TEXT NOT NULL,
                    method TEXT,
                    file_path TEXT,
                    error TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );
            """)
            conn.commit()

    def start_session(self, total_tracks: int) -> int:
        """Create a new download session and return its ID."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO sessions (started_at, status, total_tracks, completed, failed)
                VALUES (?, 'running', ?, 0, 0)
                """,
                (now, total_tracks),
            )
            conn.commit()
            session_id = cursor.lastrowid
            logger.info(f"Started new download session #{session_id} for {total_tracks} tracks.")
            return session_id

    def checkpoint(
        self,
        session_id: int,
        spotify_id: str,
        status: str,
        method: Optional[str] = None,
        file_path: Optional[str] = None,
        error: Optional[str] = None,
    ):
        """Record atomic checkpoint for a track."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            # Upsert into download_checkpoints
            conn.execute(
                """
                INSERT INTO download_checkpoints (spotify_id, session_id, status, method, file_path, error, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(spotify_id) DO UPDATE SET
                    session_id=excluded.session_id,
                    status=excluded.status,
                    method=excluded.method,
                    file_path=excluded.file_path,
                    error=excluded.error,
                    timestamp=excluded.timestamp;
                """,
                (spotify_id, session_id, status, method, file_path, error, now),
            )

            # Update session aggregates
            if status == "completed":
                conn.execute(
                    "UPDATE sessions SET completed = completed + 1, last_track_id = ? WHERE id = ?",
                    (spotify_id, session_id),
                )
            else:
                conn.execute(
                    "UPDATE sessions SET failed = failed + 1, last_track_id = ? WHERE id = ?",
                    (spotify_id, session_id),
                )
            conn.commit()

    def end_session(self, session_id: int, status: str = "completed"):
        """Mark a session as finished."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE sessions SET status = ?, ended_at = ? WHERE id = ?",
                (status, now, session_id),
            )
            conn.commit()
            logger.info(f"Finished download session #{session_id} with status '{status}'.")

    def get_completed_spotify_ids(self) -> Set[str]:
        """Return the set of all spotify_ids marked as 'completed' in checkpoint database."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT spotify_id FROM download_checkpoints WHERE status = 'completed'")
            return {row["spotify_id"] for row in cursor.fetchall()}

    def get_last_active_session(self) -> Optional[Dict[str, Any]]:
        """Retrieve the most recent session info."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM sessions ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_session_stats(self) -> Dict[str, Any]:
        """Return overall checkpoint stats."""
        with self._get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) as c FROM download_checkpoints").fetchone()["c"]
            completed = conn.execute("SELECT COUNT(*) as c FROM download_checkpoints WHERE status = 'completed'").fetchone()["c"]
            failed = conn.execute("SELECT COUNT(*) as c FROM download_checkpoints WHERE status = 'failed'").fetchone()["c"]
            sessions_count = conn.execute("SELECT COUNT(*) as c FROM sessions").fetchone()["c"]

            return {
                "total_checkpoints": total,
                "completed_checkpoints": completed,
                "failed_checkpoints": failed,
                "total_sessions": sessions_count,
            }
