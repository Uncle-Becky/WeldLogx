"""Seed the WeldLogx database with sample data for demos."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from weld_tracker import (
    add_segment,
    add_seam,
    add_welder,
    get_connection,
    initialize_database,
    log_entry,
)


def main() -> None:
    conn = get_connection()
    initialize_database(conn)

    add_welder(conn, "W100", "Alex Root")
    add_welder(conn, "W200", "Bailey Fill")
    add_welder(conn, "W300", "Casey Cap")

    add_seam(conn, "SEAM-01", "North pipeline header", customer="ACME Energy")
    add_segment(conn, "SEAM-01", 1, 0.0, 12.5, ["Root", "Fill", "Cap"])
    add_segment(conn, "SEAM-01", 2, 12.5, 25.0, ["Root", "Fill", "Cap"])

    now = datetime.now(timezone.utc)
    log_entry(conn, seam_id="SEAM-01", segment_no=1, pass_name="Root", action="Start", welder_id="W100", timestamp=now - timedelta(hours=5), shift="Day")
    log_entry(conn, seam_id="SEAM-01", segment_no=1, pass_name="Root", action="Complete", welder_id="W100", timestamp=now - timedelta(hours=4), shift="Day")
    log_entry(conn, seam_id="SEAM-01", segment_no=1, pass_name="Fill", action="Complete", welder_id="W200", timestamp=now - timedelta(hours=2), shift="Swing")
    log_entry(conn, seam_id="SEAM-01", segment_no=2, pass_name="Root", action="Start", welder_id="W100", timestamp=now - timedelta(hours=1), shift="Swing")

    print("Seed data applied. Launch Streamlit with `streamlit run weld_tracker_app.py`.")
    conn.close()


if __name__ == "__main__":
    main()
