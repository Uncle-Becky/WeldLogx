from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pandas as pd

from weld_tracker import (
    add_segment,
    add_seam,
    add_welder,
    get_connection,
    initialize_database,
    list_segments_with_status,
    log_entry,
    recompute_segments,
)


def create_db(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(db_path)
    initialize_database(conn)
    return conn


def seed_baseline(conn):
    add_welder(conn, "W1", "Welder One")
    add_welder(conn, "W2", "Welder Two")
    add_seam(conn, "S1", "Test seam")
    add_segment(conn, "S1", 1, 0.0, 10.0, ["Root", "Fill", "Cap"])


def test_recompute_idempotent(tmp_path):
    conn = create_db(tmp_path)
    seed_baseline(conn)
    log_entry(conn, seam_id="S1", segment_no=1, pass_name="Root", action="Start", welder_id="W1")
    log_entry(conn, seam_id="S1", segment_no=1, pass_name="Root", action="Complete", welder_id="W1")
    log_entry(conn, seam_id="S1", segment_no=1, pass_name="Fill", action="Complete", welder_id="W2")

    recompute_segments(conn)
    first = list_segments_with_status(conn)
    recompute_segments(conn)
    second = list_segments_with_status(conn)

    pd.testing.assert_frame_equal(first, second)
    conn.close()


def test_complete_overwrites_prior_complete(tmp_path):
    conn = create_db(tmp_path)
    seed_baseline(conn)
    earlier = datetime.now(timezone.utc) - timedelta(hours=1)
    later = datetime.now(timezone.utc)

    log_entry(
        conn,
        seam_id="S1",
        segment_no=1,
        pass_name="Root",
        action="Complete",
        welder_id="W1",
        timestamp=earlier,
    )
    log_entry(
        conn,
        seam_id="S1",
        segment_no=1,
        pass_name="Root",
        action="Complete",
        welder_id="W2",
        timestamp=later,
    )

    recompute_segments(conn)
    status_df = list_segments_with_status(conn)
    row = status_df.iloc[0]
    assert row["root_by"] == "W2"
    conn.close()


def test_start_without_complete_sets_in_progress(tmp_path):
    conn = create_db(tmp_path)
    seed_baseline(conn)
    log_entry(conn, seam_id="S1", segment_no=1, pass_name="Fill", action="Start", welder_id="W1")

    recompute_segments(conn)
    status_df = list_segments_with_status(conn)
    row = status_df.iloc[0]
    assert row["segment_status"] == "In progress"
    assert row["percent_complete"] == 0
    conn.close()
