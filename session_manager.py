#!/usr/bin/env python3
"""
JAIMES AI Executive - Redis Session Management
Handles persistent storage of conversation sessions using Redis.
"""

import json
import logging
from typing import Optional
from datetime import datetime
from dataclasses import asdict
from tenacity import (
    retry,
    RetryCallState,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import redis.exceptions
from utils import send_discord_alert
from models import JAIMESSession  # Import JAIMESSession from models.py

# This assumes your JAIMESSession model is in this file.
# When you restructure your project, you'll change this to `from models.schemas import JAIMESSession`.
from complete_jaimes_with_customer_recognition import JAIMESSession

# It's recommended to install redis with: pip install redis
try:
    import redis
except ImportError:
    print("Redis library not found. Please install it with: pip install redis")
    redis = None

logger = logging.getLogger(__name__)


class SessionMonitor:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.redis_severity = "SUCCESS"
        self.groq_severity = "SUCCESS"
        self.notes = []

    def update_redis_severity(self, level: str, note: str = ""):
        self.redis_severity = level
        if note:
            self.notes.append(f"Redis: {note}")

    def update_groq_severity(self, level: str, note: str = ""):
        self.groq_severity = level
        if note:
            self.notes.append(f"Groq: {note}")

    def get_overall_severity(self) -> str:
        levels = [self.redis_severity, self.groq_severity]
        if "FAILURE" in levels:
            return "FAILURE"
        elif "MAJOR" in levels:
            return "MAJOR"
        elif "MINOR" in levels:
            return "MINOR"
        return "SUCCESS"


class SessionMonitor:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.redis_severity = "SUCCESS"
        self.groq_severity = "SUCCESS"
        self.notes = []
        self.total_latency = None  # ✅ 2. Initialize the latency variable

    # ... (your other methods like update_redis_severity) ...

    def set_total_latency(self, latency_ms: int):
        self.total_latency = latency_ms

    def report_embed(self):
        # ... (color_map and emoji_map definitions are fine) ...
        severity = self.get_overall_severity()
        color_map = {
            "SUCCESS": 0x2ECC71,
            "MINOR": 0xF1C40F,
            "MAJOR": 0xE67E22,
            "FAILURE": 0xE74C3C,
        }
        emoji_map = {
            "SUCCESS": "✅ JAIMES ran like a dream",
            "MINOR": "⚠️ JAIMES had a minor hiccup",
            "MAJOR": "🔥 JAIMES nearly coughed up a bolt",
            "FAILURE": "❌ JAIMES broke down mid-session",
        }

        # ✅ 3. Ensure this block is indented correctly
        embed = {
            "title": "Session Diagnostic Report",
            "description": emoji_map.get(severity, "🔧 JAIMES ran diagnostics"),
            "color": color_map.get(severity, 0x95A5A6),
            "fields": [
                {
                    "name": "Session ID",
                    "value": f"`{self.session_id}`",
                    "inline": False,
                },
                {"name": "Redis Health", "value": self.redis_severity, "inline": True},
                {"name": "Groq Health", "value": self.groq_severity, "inline": True},
                # ✅ 4. Use the consistent variable name 'self.total_latency'
                {
                    "name": "Total Latency",
                    "value": (
                        f"{self.total_latency} ms"
                        if self.total_latency is not None
                        else "N/A"
                    ),
                    "inline": False,
                },
            ],
            "footer": {"text": "JAIMES Diagnostic Telemetry"},
            "timestamp": datetime.utcnow().isoformat(),
        }

        # ✅ 5. Add the action step to send the embed
        send_discord_alert(embed=embed)
        if self.notes:
            embed["fields"].append(
                {"name": "Notes", "value": "\n".join(self.notes), "inline": False}
            )

        send_discord_alert(embed=embed)


class RedisSessionManager:
    """Manages the lifecycle of conversation sessions using Redis."""

    def __init__(self, redis_url: str):
        """Initializes the Redis client and checks the connection."""
        if not redis:
            raise ImportError("The 'redis' library is required but not installed.")
        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()
            logger.info("Successfully connected to Redis server.")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise  # Re-raise exception to halt startup if Redis is unavailable

    def _log_retry_attempt(self, retry_state: RetryCallState):
        """Logs a warning to the console before a retry attempt."""
        logger.warning(
            f"Redis connection error, attempt {retry_state.attempt_number} failed. Retrying..."
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, max=10),
        retry=retry_if_exception_type(redis.exceptions.ConnectionError),
        before_sleep=_log_retry_attempt,  # ✅ Correctly logs before each retry
    )
    def get_session(self, session_id: str) -> Optional["JAIMESSession"]:
        """Retrieves a session from Redis by its ID."""
        session_key = f"session:{session_id}"
        session_data = self.redis_client.get(session_key)
        if session_data:
            logger.info(f"Session cache HIT for session_id: {session_id}")
            # Replace JAIMESSession with your actual session class
            return JAIMESSession(**json.loads(session_data))
        else:
            logger.info(f"Session cache MISS for session_id: {session_id}")
            return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, max=10),
        retry=retry_if_exception_type(redis.exceptions.ConnectionError),
        before_sleep=_log_retry_attempt,
    )
    def save_session(self, session_id: str, session_obj: "JAIMESSession") -> None:
        """Saves a session object to Redis."""
        session_key = f"session:{session_id}"
        # A more robust method would be to use Pydantic's .model_dump_json() if available
        session_data = session_obj.model_dump_json()  # Use Pydantic's optimized method
        self.redis_client.set(session_key, session_data)
        logger.info(f"Session saved for session_id: {session_id}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, max=10),
        retry=retry_if_exception_type(redis.exceptions.ConnectionError),
        before_sleep=_log_retry_attempt,
    )
    def delete_session(self, session_id: str) -> None:
        """Deletes a session from Redis."""
        session_key = f"session:{session_id}"
        self.redis_client.delete(session_key)
        logger.info(f"Session deleted for session_id: {session_id}")


# --- In-Memory Monitoring for a Single Session ---


class SessionMonitor:
    """Monitors the health and performance of a single request session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.redis_severity = "SUCCESS"
        self.groq_severity = "SUCCESS"
        self.notes = []
        self.total_latency = None
        self.redis_latency = None
        self.groq_latency = None

    def update_redis_severity(self, level: str, note: str = ""):
        self.redis_severity = level
        if note:
            self.notes.append(f"Redis: {note}")

    def update_groq_severity(self, level: str, note: str = ""):
        self.groq_severity = level
        if note:
            self.notes.append(f"Groq: {note}")

    def set_total_latency(self, latency_ms: int):
        self.total_latency = latency_ms

    def set_redis_latency(self, latency_ms: int):
        self.redis_latency = latency_ms

    def set_groq_latency(self, latency_ms: int):
        self.groq_latency = latency_ms

    def get_overall_severity(self) -> str:
        levels = [self.redis_severity, self.groq_severity]
        if "FAILURE" in levels:
            return "FAILURE"
        if "MAJOR" in levels:
            return "MAJOR"
        if "MINOR" in levels:
            return "MINOR"
        return "SUCCESS"

    def report_embed(self):
        """Builds and sends a diagnostic report embed to Discord."""
        severity = self.get_overall_severity()
        color_map = {
            "SUCCESS": 0x2ECC71,
            "MINOR": 0xF1C40F,
            "MAJOR": 0xE67E22,
            "FAILURE": 0xE74C3C,
        }
        emoji_map = {
            "SUCCESS": "✅ JAIMES ran like a dream",
            "MINOR": "⚠️ JAIMES had a minor hiccup",
            "MAJOR": "🔥 JAIMES nearly coughed up a bolt",
            "FAILURE": "❌ JAIMES broke down mid-session",
        }

        embed = {
            "title": "Session Diagnostic Report",
            "description": emoji_map.get(severity, "🔧 JAIMES ran diagnostics"),
            "color": color_map.get(severity, 0x95A5A6),
            "fields": [
                {
                    "name": "Session ID",
                    "value": f"`{self.session_id}`",
                    "inline": False,
                },
                {"name": "Redis Health", "value": self.redis_severity, "inline": True},
                {"name": "Groq Health", "value": self.groq_severity, "inline": True},
                {
                    "name": "Total Latency",
                    "value": (
                        f"{self.total_latency} ms"
                        if self.total_latency is not None
                        else "N/A"
                    ),
                    "inline": True,
                },
                {
                    "name": "Groq Latency",
                    "value": (
                        f"{self.groq_latency} ms"
                        if self.groq_latency is not None
                        else "N/A"
                    ),
                    "inline": True,
                },
                {
                    "name": "Redis Latency",
                    "value": (
                        f"{self.redis_latency} ms"
                        if self.redis_latency is not None
                        else "N/A"
                    ),
                    "inline": True,
                },
            ],
            "footer": {"text": "JAIMES Diagnostic Telemetry"},
            "timestamp": datetime.utcnow().isoformat(),
        }

        if self.notes:
            embed["fields"].append(
                {"name": "Notes", "value": "\n".join(self.notes), "inline": False}
            )

        send_discord_alert(embed=embed)
