"""
database_setup.py — ELCIA Monsoon Intelligence
================================================
Creates the SQLite database (events.db) with the `incidents` table
and seeds it with sample records for testing.

Usage:
    python3 database_setup.py          # create + seed
    python3 database_setup.py --reset  # drop, recreate, re-seed
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "events.db"

# ── Schema ───────────────────────────────────────────────────────────────────
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS incidents (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp        TEXT    NOT NULL,
    zone             TEXT    NOT NULL,
    hazard_class     TEXT    NOT NULL,
    confidence_score REAL    NOT NULL,
    severity_score   REAL    NOT NULL,
    thumbnail_path   TEXT,
    status           TEXT    NOT NULL DEFAULT 'Open'
);
"""

DROP_TABLE_SQL = "DROP TABLE IF EXISTS incidents;"

# ── Sample records ───────────────────────────────────────────────────────────
def _sample_records() -> list[tuple]:
    """Return 4 hand-crafted sample incidents with varying severities."""
    now = datetime.now()
    return [
        # High severity — pothole on a major road
        (
            (now - timedelta(hours=1, minutes=12)).isoformat(timespec="seconds"),
            "Hosur Road Sector A",
            "pothole",
            0.92,
            0.85,
            "thumbnails/pothole_hosur_001.jpg",
            "Open",
        ),
        # High severity — drain overflow near underpass
        (
            (now - timedelta(hours=3, minutes=45)).isoformat(timespec="seconds"),
            "Silk Board Underpass",
            "drain_overflow",
            0.88,
            0.74,
            "thumbnails/drain_silkboard_002.jpg",
            "Open",
        ),
        # Medium severity — waterlogged stretch
        (
            (now - timedelta(hours=6, minutes=20)).isoformat(timespec="seconds"),
            "Koramangala 5th Block",
            "waterlogged_road",
            0.79,
            0.45,
            "thumbnails/waterlog_koramangala_003.jpg",
            "Acknowledged",
        ),
        # Low severity — minor footpath damage
        (
            (now - timedelta(hours=10, minutes=5)).isoformat(timespec="seconds"),
            "Jayanagar 4th Block",
            "damaged_footpath",
            0.65,
            0.18,
            "thumbnails/footpath_jayanagar_004.jpg",
            "Resolved",
        ),
    ]


# ── Public helpers (importable by other scripts) ─────────────────────────────
def get_connection() -> sqlite3.Connection:
    """Return a connection to the events database."""
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)


def create_table(conn: sqlite3.Connection) -> None:
    """Create the incidents table (idempotent)."""
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()


def insert_incident(
    conn: sqlite3.Connection,
    timestamp: str,
    zone: str,
    hazard_class: str,
    confidence_score: float,
    severity_score: float,
    thumbnail_path: str = "",
    status: str = "Open",
) -> int:
    """Insert a single incident and return its id."""
    cur = conn.execute(
        """
        INSERT INTO incidents
            (timestamp, zone, hazard_class, confidence_score,
             severity_score, thumbnail_path, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (timestamp, zone, hazard_class, confidence_score,
         severity_score, thumbnail_path, status),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def seed_sample_data(conn: sqlite3.Connection) -> int:
    """Insert the built-in sample records. Returns count inserted."""
    records = _sample_records()
    conn.executemany(
        """
        INSERT INTO incidents
            (timestamp, zone, hazard_class, confidence_score,
             severity_score, thumbnail_path, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        records,
    )
    conn.commit()
    return len(records)


def update_status(conn: sqlite3.Connection, incident_id: int, new_status: str) -> None:
    """Update the status of an incident by id."""
    conn.execute(
        "UPDATE incidents SET status = ? WHERE id = ?",
        (new_status, incident_id),
    )
    conn.commit()


def fetch_all(conn: sqlite3.Connection) -> list[tuple]:
    """Return all incidents ordered by timestamp descending."""
    return conn.execute(
        "SELECT * FROM incidents ORDER BY timestamp DESC"
    ).fetchall()


# ── CLI entry point ──────────────────────────────────────────────────────────
def main() -> None:
    reset = "--reset" in sys.argv

    conn = get_connection()

    if reset:
        conn.execute(DROP_TABLE_SQL)
        conn.commit()
        print("🗑️   Dropped existing incidents table.")

    create_table(conn)
    print(f"✅  Table 'incidents' ready in {DB_PATH}")

    # Only seed if the table is empty (disabled for production)
    row_count = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
    print(f"ℹ️   Table has {row_count} record(s). Starting clean.")

    # Print what's in the table
    print("\n── Current incidents ──────────────────────────────────")
    print(f"{'ID':<4} {'Timestamp':<22} {'Zone':<24} {'Class':<20} "
          f"{'Conf':>5} {'Sev':>5} {'Status':<14}")
    print("─" * 100)
    for row in fetch_all(conn):
        rid, ts, zone, cls, conf, sev, thumb, status = row
        print(f"{rid:<4} {ts:<22} {zone:<24} {cls:<20} "
              f"{conf:>5.2f} {sev:>5.2f} {status:<14}")

    conn.close()


if __name__ == "__main__":
    main()
