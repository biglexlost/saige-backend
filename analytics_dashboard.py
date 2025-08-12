#!/usr/bin/env python3
"""
Analytics Dashboard (CLI)
Reads conversation_analytics.db and prints weekly/monthly KPIs.
"""
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict

DB_PATH = "conversation_analytics.db"


def _count_events(conn, event_name: str, since: datetime) -> int:
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM events WHERE event_name = ? AND timestamp >= ?",
        (event_name, since.isoformat(timespec="seconds")),
    )
    return cur.fetchone()[0] or 0


def _avg_call_duration_ms(conn, since: datetime) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT AVG(CAST(json_extract(payload_json, '$.duration_ms') AS REAL))
        FROM events
        WHERE event_name = 'call_ended' AND timestamp >= ?
        """,
        (since.isoformat(timespec="seconds"),),
    )
    val = cur.fetchone()[0]
    return int(val or 0)


def _conversion(conn, since: datetime):
    cur = conn.cursor()
    # estimate_accepted that lead to schedule_confirmed (by session)
    cur.execute(
        """
        SELECT ea.session_id
        FROM events ea
        WHERE ea.event_name = 'estimate_accepted' AND ea.timestamp >= ?
        """,
        (since.isoformat(timespec="seconds"),),
    )
    accepted_sessions = {row[0] for row in cur.fetchall()}

    cur.execute(
        """
        SELECT sc.session_id
        FROM events sc
        WHERE sc.event_name = 'schedule_confirmed' AND sc.timestamp >= ?
        """,
        (since.isoformat(timespec="seconds"),),
    )
    scheduled_sessions = {row[0] for row in cur.fetchall()}

    accepted_then_scheduled = len(accepted_sessions & scheduled_sessions)

    # estimate_declined that still scheduled
    cur.execute(
        """
        SELECT ed.session_id
        FROM events ed
        WHERE ed.event_name = 'estimate_declined' AND ed.timestamp >= ?
        """,
        (since.isoformat(timespec="seconds"),),
    )
    declined_sessions = {row[0] for row in cur.fetchall()}
    declined_then_scheduled = len(declined_sessions & scheduled_sessions)

    return accepted_then_scheduled, declined_then_scheduled


def print_dashboard(period_name: str, days_back: int):
    since = datetime.utcnow() - timedelta(days=days_back)
    conn = sqlite3.connect(DB_PATH)

    scheduled = _count_events(conn, "schedule_confirmed", since)
    estimates = _count_events(conn, "estimate_shown", since)
    declined = _count_events(conn, "estimate_declined", since)
    accepted_scheduled, declined_scheduled = _conversion(conn, since)
    avg_duration_ms = _avg_call_duration_ms(conn, since)

    print("\n=== JAIMES Analytics Dashboard —", period_name, "===")
    print("Since:", since.strftime("%Y-%m-%d %H:%M UTC"))
    print(f"Appointments scheduled: {scheduled}")
    print(f"Estimates shown:       {estimates}")
    print(f"Estimates declined:    {declined}")
    print(f"Accepted→Scheduled:    {accepted_scheduled}")
    print(f"Declined→Scheduled:    {declined_scheduled}")
    print(f"Avg call length:       {round(avg_duration_ms/1000, 1)} sec")

    conn.close()


if __name__ == "__main__":
    print_dashboard("Last 7 days", 7)
    print_dashboard("Last 30 days", 30)
