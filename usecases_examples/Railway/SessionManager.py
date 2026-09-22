"""
SessionManager.py — Manages user sessions, scenario ordering, and decision logging.

Each session:
- Gets a random ordering of the 4 scenarios
- Tracks which scenario is current
- Logs all decisions to SQLite

Logging schema:
    decisions(id, session_id, scenario_id, decision_index,
              option_index, option_label, timestamp)
"""

import sqlite3
import random
import uuid
from datetime import datetime, timezone


DB_PATH = "sessions.db"


def _init_db():
    """Create all tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id    TEXT    NOT NULL,
            scenario_id   TEXT    NOT NULL,
            decision_index INTEGER NOT NULL,
            option_index  INTEGER NOT NULL,
            option_label  TEXT    NOT NULL,
            timestamp     TEXT    NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id      TEXT PRIMARY KEY,
            scenario_order  TEXT NOT NULL,
            current_index   INTEGER NOT NULL DEFAULT 0,
            acronym         TEXT    NOT NULL DEFAULT '',
            mode            TEXT    NOT NULL DEFAULT 'recommendation',
            started_at      TEXT    NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reflections (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      TEXT    NOT NULL,
            acronym         TEXT    NOT NULL DEFAULT '',
            question_index  INTEGER NOT NULL,
            question_text   TEXT    NOT NULL,
            answer          TEXT    NOT NULL,
            timestamp       TEXT    NOT NULL
        )
    """)
    # Migrate existing sessions table if needed
    try:
        conn.execute("ALTER TABLE sessions ADD COLUMN acronym TEXT NOT NULL DEFAULT ''")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE sessions ADD COLUMN mode TEXT NOT NULL DEFAULT 'recommendation'")
    except Exception:
        pass
    conn.commit()
    conn.close()


_init_db()

# In-memory session state — maps session_id to dict
_sessions: dict = {}


class SessionManager:

    @staticmethod
    def create_session(scenario_ids: list, acronym: str = "", mode: str = "recommendation") -> str:
        """
        Create a new session with a random scenario order.
        Returns the session_id.
        """
        session_id    = str(uuid.uuid4())
        shuffled      = list(scenario_ids)
        random.shuffle(shuffled)
        started_at    = datetime.now(timezone.utc).isoformat()

        # Store in memory
        _sessions[session_id] = {
            "scenario_order": shuffled,
            "current_index":  0,
            "acronym":        acronym,
            "mode":           mode,
            "started_at":     started_at,
        }

        # Persist to SQLite
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO sessions (session_id, scenario_order, current_index, acronym, mode, started_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, ",".join(shuffled), 0, acronym, mode, started_at)
        )
        conn.commit()
        conn.close()

        return session_id

    @staticmethod
    def get_session(session_id: str) -> dict | None:
        """Return session dict or None if not found."""
        return _sessions.get(session_id)

    @staticmethod
    def current_scenario_id(session_id: str) -> str | None:
        """Return the ID of the current scenario for this session."""
        session = _sessions.get(session_id)
        if session is None:
            return None
        idx   = session["current_index"]
        order = session["scenario_order"]
        if idx >= len(order):
            return None
        return order[idx]

    @staticmethod
    def advance_scenario(session_id: str) -> bool:
        """
        Move to the next scenario.
        Returns True if there is a next scenario, False if all done.
        """
        session = _sessions.get(session_id)
        if session is None:
            return False

        session["current_index"] += 1

        # Persist
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "UPDATE sessions SET current_index = ? WHERE session_id = ?",
            (session["current_index"], session_id)
        )
        conn.commit()
        conn.close()

        return session["current_index"] < len(session["scenario_order"])

    @staticmethod
    def log_decision(
        session_id: str,
        scenario_id: str,
        decision_index: int,
        option_index: int,
        option_label: str,
    ):
        """Log a decision to SQLite."""
        timestamp = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO decisions "
            "(session_id, scenario_id, decision_index, option_index, option_label, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, scenario_id, decision_index, option_index, option_label, timestamp)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def log_reflection(
        session_id: str,
        acronym: str,
        answers: list,  # list of {question_index, question_text, answer}
    ):
        """Log reflection module answers to SQLite."""
        timestamp = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(DB_PATH)
        for a in answers:
            conn.execute(
                "INSERT INTO reflections "
                "(session_id, acronym, question_index, question_text, answer, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, acronym,
                 a.get("question_index", 0),
                 a.get("question_text", ""),
                 a.get("answer", ""),
                 timestamp)
            )
        conn.commit()
        conn.close()

    @staticmethod
    def get_reflections(session_id: str) -> list:
        """Return reflection answers for a session."""
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT question_index, question_text, answer, timestamp "
            "FROM reflections WHERE session_id = ? ORDER BY id",
            (session_id,)
        ).fetchall()
        conn.close()
        return [{"question_index": r[0], "question_text": r[1],
                 "answer": r[2], "timestamp": r[3]} for r in rows]

    @staticmethod
    def get_decisions(session_id: str) -> list:
        """Return all decisions for a session (for end screen)."""
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT scenario_id, decision_index, option_index, option_label, timestamp "
            "FROM decisions WHERE session_id = ? ORDER BY id",
            (session_id,)
        ).fetchall()
        conn.close()
        return [
            {
                "scenario_id":    row[0],
                "decision_index": row[1],
                "option_index":   row[2],
                "option_label":   row[3],
                "timestamp":      row[4],
            }
            for row in rows
        ]

    @staticmethod
    def is_complete(session_id: str) -> bool:
        """Return True if all scenarios have been played."""
        session = _sessions.get(session_id)
        if session is None:
            return True
        return session["current_index"] >= len(session["scenario_order"])

    @staticmethod
    def sessions_summary() -> list:
        """Return all sessions (for admin/research export)."""
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT session_id, scenario_order, current_index, started_at FROM sessions"
        ).fetchall()
        conn.close()
        return [
            {
                "session_id":     row[0],
                "scenario_order": row[1].split(","),
                "current_index":  row[2],
                "started_at":     row[3],
            }
            for row in rows
        ]
