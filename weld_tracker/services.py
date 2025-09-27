"""Domain services implementing core business logic."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd

from .validation import validate_entry_inputs

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def add_welder(conn: sqlite3.Connection, welder_id: str, name: str) -> None:
    welder_id = welder_id.strip()
    name = name.strip()
    if not welder_id:
        raise ValueError("Welder ID is required")
    if not name:
        raise ValueError("Welder name is required")
    with conn:
        conn.execute(
            """
            INSERT INTO welders(welder_id, name)
            VALUES(?, ?)
            ON CONFLICT(welder_id) DO UPDATE SET name=excluded.name
            """,
            (welder_id, name),
        )


def add_seam(conn: sqlite3.Connection, seam_id: str, description: str = "", customer: str = "") -> None:
    seam_id = seam_id.strip()
    if not seam_id:
        raise ValueError("Seam ID is required")
    with conn:
        conn.execute(
            """
            INSERT INTO seams(seam_id, description, customer)
            VALUES(?, ?, ?)
            ON CONFLICT(seam_id) DO UPDATE
                SET description=excluded.description,
                    customer=excluded.customer
            """,
            (seam_id, description.strip(), customer.strip()),
        )


def add_segment(
    conn: sqlite3.Connection,
    seam_id: str,
    segment_no: int,
    start_in: float,
    end_in: float,
    pass_list: Iterable[str],
) -> None:
    passes = "|".join(p.strip() for p in pass_list if p.strip())
    if not passes:
        raise ValueError("At least one pass is required")
    with conn:
        conn.execute(
            """
            INSERT INTO segments(seam_id, segment_no, start_in, end_in, pass_list)
            VALUES(?, ?, ?, ?, ?)
            ON CONFLICT(seam_id, segment_no) DO UPDATE
                SET start_in=excluded.start_in,
                    end_in=excluded.end_in,
                    pass_list=excluded.pass_list
            """,
            (seam_id, segment_no, float(start_in), float(end_in), passes),
        )


def get_passes_for_seam(conn: sqlite3.Connection, seam_id: str) -> List[str]:
    row = conn.execute(
        "SELECT pass_list FROM segments WHERE seam_id=? LIMIT 1", (seam_id,)
    ).fetchone()
    if not row:
        return []
    return [p.strip() for p in row[0].split("|") if p.strip()]


def list_welders(conn: sqlite3.Connection) -> List[dict]:
    cur = conn.execute(
        "SELECT welder_id, name, active, created_at FROM welders ORDER BY name"
    )
    return [
        {
            "welder_id": row[0],
            "name": row[1],
            "active": bool(row[2]),
            "created_at": row[3],
        }
        for row in cur.fetchall()
    ]


def list_seams(conn: sqlite3.Connection) -> List[dict]:
    cur = conn.execute(
        "SELECT seam_id, description, customer, created_at FROM seams ORDER BY seam_id"
    )
    return [
        {
            "seam_id": row[0],
            "description": row[1],
            "customer": row[2],
            "created_at": row[3],
        }
        for row in cur.fetchall()
    ]


def log_entry(
    conn: sqlite3.Connection,
    *,
    seam_id: str,
    segment_no: int,
    pass_name: str,
    action: str,
    welder_id: str,
    timestamp: Optional[datetime] = None,
    shift: Optional[str] = None,
    notes: str = "",
) -> None:
    timestamp = timestamp or datetime.now(timezone.utc)
    validate_entry_inputs(conn, seam_id, segment_no, pass_name, action, welder_id)
    with conn:
        conn.execute(
            """
            INSERT INTO entries(timestamp, seam_id, segment_no, pass, action, welder_id, shift, notes)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp.astimezone(timezone.utc).isoformat(timespec="milliseconds"),
                seam_id,
                segment_no,
                pass_name,
                action,
                welder_id,
                shift,
                notes.strip(),
            ),
        )


def list_entries(conn: sqlite3.Connection, limit: int = 500) -> pd.DataFrame:
    query = """
        SELECT
            e.timestamp,
            e.seam_id,
            e.segment_no,
            e.pass,
            e.action,
            e.welder_id,
            w.name AS welder_name,
            e.shift,
            e.notes
        FROM entries e
        LEFT JOIN welders w ON w.welder_id = e.welder_id
        ORDER BY datetime(e.timestamp) DESC
        LIMIT ?
    """
    df = pd.read_sql_query(query, conn, params=(limit,))
    return df


def list_segments_with_status(conn: sqlite3.Connection) -> pd.DataFrame:
    from .status import compute_segment_status

    segments_df = pd.read_sql_query(
        "SELECT * FROM segments",
        conn,
    )
    entries_df = pd.read_sql_query(
        "SELECT * FROM entries",
        conn,
    )
    return compute_segment_status(segments_df, entries_df)


def recompute_segments(conn: sqlite3.Connection) -> None:
    """Materialise derived status fields for compatibility."""
    result = list_segments_with_status(conn)
    updates = [
        (
            row.segment_status,
            float(row.percent_complete),
            row.root_by,
            row.root_at,
            row.fill_by,
            row.fill_at,
            row.cap_by,
            row.cap_at,
            row.seam_id,
            row.segment_no,
        )
        for row in result.itertuples()
    ]
    with conn:
        conn.executemany(
            """
            UPDATE segments
               SET segment_status=?,
                   percent_complete=?,
                   root_by=?, root_at=?,
                   fill_by=?, fill_at=?,
                   cap_by=?, cap_at=?
             WHERE seam_id=? AND segment_no=?
            """,
            updates,
        )


def export_database_copy(conn: sqlite3.Connection, target_dir: Path) -> Path:
    target_dir = target_dir.expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = target_dir / f"weldtracker-backup-{timestamp}.db"
    quoted_path = str(destination).replace("'", "''")
    with conn:
        conn.execute(f"VACUUM INTO '{quoted_path}'")
    return destination


__all__ = [
    "add_welder",
    "add_seam",
    "add_segment",
    "get_passes_for_seam",
    "list_welders",
    "list_seams",
    "log_entry",
    "list_entries",
    "list_segments_with_status",
    "recompute_segments",
    "export_database_copy",
]
