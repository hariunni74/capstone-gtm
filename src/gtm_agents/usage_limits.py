"""Limit daily research attempts using a persistent SQLite counter."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_FILE = Path(__file__).resolve().parents[2] / "logs" / "usage.sqlite3"


def reserve_run(run_id: str, daily_limit: int) -> bool:
    """Reserve one attempt atomically; failed attempts also count."""
    if daily_limit < 1:
        raise ValueError("Daily run limit must be at least 1.")

    # Reset the allowance at midnight UTC.
    today = datetime.now(timezone.utc).date().isoformat()
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        DB_FILE, timeout=10, isolation_level=None
    )
    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS run_attempts (
                run_id TEXT PRIMARY KEY,
                day TEXT NOT NULL
            )
        """)

        # Prevent simultaneous submissions from exceeding the limit.
        connection.execute("BEGIN IMMEDIATE")

        existing = connection.execute(
            "SELECT 1 FROM run_attempts WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if existing:
            connection.rollback()
            return False

        count = connection.execute(
            "SELECT COUNT(*) FROM run_attempts WHERE day = ?",
            (today,),
        ).fetchone()[0]

        if count >= daily_limit:
            connection.rollback()
            return False

        connection.execute(
            "INSERT INTO run_attempts (run_id, day) VALUES (?, ?)",
            (run_id, today),
        )
        connection.commit()
        return True
    finally:
        connection.close()