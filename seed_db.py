"""
seed_db.py — Populate events.db with realistic sample data
===========================================================
Run once:  python seed_db.py
Re-run to reset the database with fresh random records.
"""

import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "events.db"

ZONES = [
    "Hosur Road Sector A",
    "Hosur Road Sector B",
    "MG Road Junction",
    "Koramangala 5th Block",
    "Koramangala 8th Block",
    "Indiranagar 100ft Road",
    "Whitefield Main Road",
    "Marathahalli Bridge",
    "Silk Board Underpass",
    "Jayanagar 4th Block",
    "Hebbal Flyover",
    "Electronic City Phase 1",
    "Bellandur Gate",
    "KR Puram Railway Bridge",
    "Yelahanka New Town",
]

CLASSES = ["pothole", "waterlogged_road", "drain_overflow", "damaged_footpath"]

CLASS_WEIGHTS = [0.35, 0.30, 0.20, 0.15]  # realistic distribution

STATUSES = ["Open", "Acknowledged", "Resolved"]
STATUS_WEIGHTS = [0.50, 0.25, 0.25]

NUM_EVENTS = 80  # number of sample rows


def create_table(conn: sqlite3.Connection) -> None:
    """Create the events table (drops existing if present)."""
    conn.execute("DROP TABLE IF EXISTS events")
    conn.execute(
        """
        CREATE TABLE events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT    NOT NULL,
            zone            TEXT    NOT NULL,
            class           TEXT    NOT NULL,
            confidence_score REAL   NOT NULL,
            severity_score  REAL    NOT NULL,
            thumbnail_path  TEXT,
            status          TEXT    NOT NULL DEFAULT 'Open'
        )
        """
    )
    conn.commit()


def generate_events(n: int) -> list[tuple]:
    """Return n realistic random event tuples."""
    now = datetime.now()
    rows = []
    for _ in range(n):
        # timestamps spread over the last 72 hours
        ts = now - timedelta(
            hours=random.uniform(0, 72),
            minutes=random.randint(0, 59),
        )
        zone = random.choice(ZONES)
        cls = random.choices(CLASSES, weights=CLASS_WEIGHTS, k=1)[0]

        # confidence between 0.55 and 0.99
        confidence = round(random.uniform(0.55, 0.99), 2)

        # severity between 0.05 and 0.98; skew toward the middle
        severity = round(random.betavariate(2, 2.5) * 0.93 + 0.05, 2)

        thumb = f"thumbnails/{cls}_{ts:%Y%m%d%H%M%S}_{random.randint(1000,9999)}.jpg"
        status = random.choices(STATUSES, weights=STATUS_WEIGHTS, k=1)[0]

        rows.append((ts.isoformat(timespec="seconds"), zone, cls, confidence, severity, thumb, status))

    # sort descending by timestamp
    rows.sort(key=lambda r: r[0], reverse=True)
    return rows


def main() -> None:
    conn = sqlite3.connect(str(DB_PATH))
    create_table(conn)

    rows = generate_events(NUM_EVENTS)
    conn.executemany(
        """
        INSERT INTO events (timestamp, zone, class, confidence_score,
                            severity_score, thumbnail_path, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()

    print(f"✅  Seeded {len(rows)} events into {DB_PATH}")


if __name__ == "__main__":
    main()
