# WeldLogx

WeldLogx is a Streamlit-based weld tracking application backed by SQLite. It captures weld events (start/complete), derives segment status from an immutable event log, and surfaces dashboards and KPIs to monitor throughput and work-in-progress.

## Features

- Event-sourced audit log for weld activity with enforced database constraints.
- Derived segment status, percent complete, and per-pass ownership.
- Operator-focused UI for logging activity, managing seams/segments/welders, and exporting backups.
- Analytics including throughput by shift, completion charts, and cycle time metrics.
- Safe SQLite migrations, WAL mode, and quick backup generation.

## Getting started

1. **Install dependencies**

   ```bash
   pip install streamlit pandas altair pytest
   ```

2. **(Optional) Seed demo data**

   ```bash
   python scripts/seed_sample_data.py
   ```

3. **Run the app**

   ```bash
   streamlit run weld_tracker_app.py
   ```

   Set the `WELDTRACKER_DB` environment variable to override the default `data/weld_tracker.db` location.

4. **Run tests**

   ```bash
   pytest
   ```

Backups can be generated from the Administration tab or via the `export_database_copy` service helper.