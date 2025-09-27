"""Streamlit application entrypoint for WeldLogx."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from weld_tracker import (
    add_segment,
    add_seam,
    add_welder,
    export_database_copy,
    get_connection,
    get_db_path,
    initialize_database,
    list_entries,
    list_segments_with_status,
    list_seams,
    list_welders,
    log_entry,
    recompute_segments,
)
from weld_tracker.analytics import build_progress_by_pass, compute_kpis
from weld_tracker.validation import ALLOWED_ACTIONS, ValidationError


st.set_page_config(page_title="WeldLogx Tracker", layout="wide")
st.title("WeldLogx – Weld Segment Tracker")

FLASH_KEY = "flash_message"


def _flash(level: str, message: str) -> None:
    st.session_state[FLASH_KEY] = (level, message)


def _consume_flash() -> None:
    flash = st.session_state.pop(FLASH_KEY, None)
    if not flash:
        return
    level, message = flash
    if level == "success":
        st.success(message)
    elif level == "error":
        st.error(message)
    elif level == "warning":
        st.warning(message)
    else:
        st.info(message)


@st.cache_resource(show_spinner=False)
def get_cached_connection() -> sqlite3.Connection:
    conn = get_connection()
    initialize_database(conn)
    return conn


HASH_FUNCS = {sqlite3.Connection: lambda _: 0}


@st.cache_data(ttl=10.0, show_spinner=False, hash_funcs=HASH_FUNCS)
def load_segments(conn: sqlite3.Connection) -> pd.DataFrame:
    return list_segments_with_status(conn)


@st.cache_data(ttl=10.0, show_spinner=False, hash_funcs=HASH_FUNCS)
def load_entries(conn: sqlite3.Connection) -> pd.DataFrame:
    return list_entries(conn, limit=1000)


@st.cache_data(ttl=10.0, show_spinner=False, hash_funcs=HASH_FUNCS)
def load_welders(conn: sqlite3.Connection) -> pd.DataFrame:
    data = list_welders(conn)
    return pd.DataFrame(data, columns=["welder_id", "name", "active", "created_at"]) if data else pd.DataFrame(columns=["welder_id", "name", "active", "created_at"])


@st.cache_data(ttl=10.0, show_spinner=False, hash_funcs=HASH_FUNCS)
def load_seams(conn: sqlite3.Connection) -> pd.DataFrame:
    data = list_seams(conn)
    return pd.DataFrame(data, columns=["seam_id", "description", "customer", "created_at"]) if data else pd.DataFrame(columns=["seam_id", "description", "customer", "created_at"])


def clear_caches() -> None:
    load_segments.clear()
    load_entries.clear()
    load_welders.clear()
    load_seams.clear()


conn = get_cached_connection()
segments_df = load_segments(conn)
entries_df = load_entries(conn)
welders_df = load_welders(conn)
seams_df = load_seams(conn)

welder_lookup = (
    dict(zip(welders_df["welder_id"], welders_df["name"]))
    if not welders_df.empty
    else {}
)

_consume_flash()


kpis = compute_kpis(segments_df, entries_df)
col1, col2, col3 = st.columns(3)
col1.metric("Segments completed today", kpis["segments_completed_today"])
col2.metric("Segments in progress", kpis["wip_segments"])
col3.metric("Avg cycle time (hrs)", f"{kpis['average_cycle_hours']:.2f}")

with st.expander("Throughput by shift", expanded=False):
    if kpis["throughput_by_shift"]:
        throughput_df = (
            pd.Series(kpis["throughput_by_shift"])
            .rename_axis("Shift")
            .reset_index(name="Completions")
        )
        st.dataframe(throughput_df, hide_index=True, use_container_width=True)
    else:
        st.info("No completion data yet.")

progress_df = build_progress_by_pass(entries_df)
if not progress_df.empty:
    chart = (
        alt.Chart(progress_df)
        .mark_bar()
        .encode(
            x="date:T",
            y="completions:Q",
            color="pass:N",
            tooltip=["date", "pass", "completions"],
        )
        .properties(height=300)
    )
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("Log work to see progress charts.")

st.subheader("Segments overview")
if not segments_df.empty:
    display_df = segments_df.copy()
    display_df["percent_complete"] = (display_df["percent_complete"] * 100).round(1)
    st.dataframe(
        display_df,
        hide_index=True,
        use_container_width=True,
    )
else:
    st.warning("No segments configured yet. Add a seam and segments below.")


tabs = st.tabs([
    "Log activity",
    "Segments & seams",
    "Welders",
    "Entries",
    "Administration",
])

with tabs[0]:
    st.header("Log weld activity")
    if seams_df.empty:
        st.info("Add seams and segments before logging activity.")
    else:
        with st.form("log_entry_form", clear_on_submit=True):
            seam_id = st.selectbox(
                "Seam",
                seams_df["seam_id"].tolist(),
            )
            segment_options = (
                segments_df[segments_df["seam_id"] == seam_id]["segment_no"].astype(int).tolist()
            )
            if segment_options:
                segment_no = st.selectbox("Segment", segment_options)
                segment_passes = (
                    segments_df[
                        (segments_df["seam_id"] == seam_id)
                        & (segments_df["segment_no"].astype(int) == int(segment_no))
                    ]["pass_list"].iloc[0]
                )
                passes = [p.strip() for p in str(segment_passes).split("|") if p.strip()]
            else:
                segment_no = None
                passes = []
            pass_name = st.selectbox("Pass", passes, disabled=not passes)
            action = st.selectbox("Action", sorted(ALLOWED_ACTIONS))
            welder_options = list(welder_lookup.keys())
            if welder_options:
                welder = st.selectbox(
                    "Welder",
                    options=welder_options,
                    format_func=lambda x: f"{x} – {welder_lookup.get(x, x)}",
                )
            else:
                welder = None
                st.warning("Add welders before logging activity.")
            shift = st.selectbox("Shift", ["", "Day", "Night", "Swing"], format_func=lambda v: v or "Unspecified")
            notes = st.text_area("Notes", placeholder="Optional details...")
            submitted = st.form_submit_button(
                "Log activity",
                disabled=not welder_options or not segment_options,
            )
        if submitted and welder and segment_no is not None:
            try:
                log_entry(
                    conn,
                    seam_id=seam_id,
                    segment_no=int(segment_no),
                    pass_name=pass_name,
                    action=action,
                    welder_id=welder,
                    shift=shift or None,
                    notes=notes,
                )
                recompute_segments(conn)
                clear_caches()
                _flash("success", "Activity logged successfully.")
                st.experimental_rerun()
            except ValidationError as exc:
                st.error(str(exc))
            except Exception as exc:  # pragma: no cover - defensive
                st.error(f"Unexpected error: {exc}")

with tabs[1]:
    st.header("Manage seams and segments")
    with st.form("add_seam_form", clear_on_submit=True):
        st.subheader("Add or update seam")
        seam_id = st.text_input("Seam ID", help="Unique identifier, e.g., SEAM-101")
        description = st.text_input("Description", placeholder="Optional seam details")
        customer = st.text_input("Customer", placeholder="Customer or project")
        submit_seam = st.form_submit_button("Save seam")
    if submit_seam:
        try:
            add_seam(conn, seam_id, description, customer)
            clear_caches()
            _flash("success", "Seam saved.")
            st.experimental_rerun()
        except ValueError as exc:
            st.error(str(exc))

    st.divider()
    if seams_df.empty:
        st.info("Add a seam above before creating segments.")
    else:
        with st.form("add_segment_form", clear_on_submit=True):
            st.subheader("Add or update segment")
            seam_choice = st.selectbox("Seam", seams_df["seam_id"].tolist(), key="segment_seam")
            segment_no = st.number_input("Segment number", min_value=1, step=1, value=1)
            start_in = st.number_input("Start (inches)", min_value=0.0, value=0.0)
            end_in = st.number_input("End (inches)", min_value=0.0, value=0.0)
            pass_list = st.text_input(
                "Pass sequence",
                value="Root|Fill|Cap",
                help="Use | to separate passes, e.g., Root|Fill|Cap",
            )
            submit_segment = st.form_submit_button("Save segment")
        if submit_segment:
            try:
                add_segment(
                    conn,
                    seam_choice,
                    int(segment_no),
                    float(start_in),
                    float(end_in),
                    pass_list.split("|"),
                )
                recompute_segments(conn)
                clear_caches()
                _flash("success", "Segment saved.")
                st.experimental_rerun()
            except ValueError as exc:
                st.error(str(exc))

    st.divider()
    st.subheader("Current seams")
    if not seams_df.empty:
        st.dataframe(seams_df, hide_index=True, use_container_width=True)
    else:
        st.info("No seams configured yet.")

with tabs[2]:
    st.header("Manage welders")
    with st.form("add_welder_form", clear_on_submit=True):
        welder_id = st.text_input("Welder ID", help="Short ID, e.g., W123")
        name = st.text_input("Welder name")
        submit_welder = st.form_submit_button("Save welder")
    if submit_welder:
        try:
            add_welder(conn, welder_id, name)
            clear_caches()
            _flash("success", "Welder saved.")
            st.experimental_rerun()
        except ValueError as exc:
            st.error(str(exc))

    if not welders_df.empty:
        st.dataframe(welders_df, hide_index=True, use_container_width=True)
    else:
        st.info("No welders yet. Add one above.")

with tabs[3]:
    st.header("Recent entries")
    if not entries_df.empty:
        st.dataframe(entries_df, hide_index=True, use_container_width=True)
        csv = entries_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download CSV",
            data=csv,
            file_name="weldlogx-entries.csv",
            mime="text/csv",
            key="entries_csv",
        )
    else:
        st.info("No activity logged yet.")

with tabs[4]:
    st.header("Administration")
    st.caption(f"Database path: {get_db_path()}")
    if st.button("Recompute segment summaries", type="primary"):
        recompute_segments(conn)
        clear_caches()
        _flash("success", "Segment cache refreshed.")
        st.experimental_rerun()

    if st.button("Create SQLite backup", key="create_backup"):
        backup_path = export_database_copy(conn, Path("backups"))
        st.session_state["latest_backup"] = str(backup_path)
        _flash("success", f"Backup created at {backup_path}")
        st.experimental_rerun()

    backup_path_str = st.session_state.get("latest_backup")
    if backup_path_str and Path(backup_path_str).exists():
        with open(backup_path_str, "rb") as handle:
            st.download_button(
                "Download latest backup",
                data=handle.read(),
                file_name=Path(backup_path_str).name,
                mime="application/octet-stream",
                key="download_backup",
            )

    st.info(
        "Backups are stored locally under the 'backups' directory. Ensure the folder is included in system backups."
    )
