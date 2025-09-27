"""Validation helpers for weld tracker operations."""
from __future__ import annotations

import sqlite3

ALLOWED_ACTIONS = {"Start", "Complete"}


class ValidationError(ValueError):
    """Domain-specific validation error."""


def _segment_exists(conn: sqlite3.Connection, seam_id: str, segment_no: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM segments WHERE seam_id=? AND segment_no=?",
        (seam_id, segment_no),
    ).fetchone()
    return bool(row)


def _welder_exists(conn: sqlite3.Connection, welder_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM welders WHERE welder_id=?",
        (welder_id,),
    ).fetchone()
    return bool(row)


def _allowed_pass(conn: sqlite3.Connection, seam_id: str, pass_name: str) -> bool:
    row = conn.execute(
        "SELECT pass_list FROM segments WHERE seam_id=? LIMIT 1",
        (seam_id,),
    ).fetchone()
    if not row:
        return False
    return pass_name in {p.strip() for p in row[0].split("|") if p.strip()}


def validate_entry_inputs(
    conn: sqlite3.Connection,
    seam_id: str,
    segment_no: int,
    pass_name: str,
    action: str,
    welder_id: str,
) -> None:
    seam_id = seam_id.strip()
    pass_name = pass_name.strip()
    action = action.strip().title()
    welder_id = welder_id.strip()

    if action not in ALLOWED_ACTIONS:
        raise ValidationError(f"Action must be one of {sorted(ALLOWED_ACTIONS)}")
    if not _segment_exists(conn, seam_id, segment_no):
        raise ValidationError("Segment does not exist; create it before logging work")
    if not _allowed_pass(conn, seam_id, pass_name):
        raise ValidationError("Pass is not valid for the selected seam")
    if not _welder_exists(conn, welder_id):
        raise ValidationError("Welder does not exist")


__all__ = ["validate_entry_inputs", "ValidationError", "ALLOWED_ACTIONS"]
