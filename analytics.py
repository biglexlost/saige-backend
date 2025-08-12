#!/usr/bin/env python3
"""
Lightweight analytics logging for JAIMES conversations.
Stores generic events in a local SQLite DB for reporting and KPIs.
"""
import sqlite3
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "conversation_analytics.db"


def init_analytics_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize the analytics database if it doesn't exist."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT NOT NULL,
                session_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
        """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_events_name_time
                ON events(event_name, timestamp)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_events_session
                ON events(session_id)
            """
        )
        conn.commit()
        conn.close()
        logger.info("Analytics DB initialized")
    except Exception as e:
        logger.error(f"Failed to initialize analytics DB: {e}")


def log_event(
    event_name: str,
    session_id: str,
    payload: Optional[Dict[str, Any]] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> None:
    """Insert a generic analytics event with a JSON payload."""
    try:
        if payload is None:
            payload = {}
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO events (event_name, session_id, timestamp, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                event_name,
                session_id,
                datetime.utcnow().isoformat(timespec="seconds"),
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to log event '{event_name}' for session {session_id}: {e}")
