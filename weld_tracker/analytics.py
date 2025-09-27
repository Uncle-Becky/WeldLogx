"""Analytics helpers for dashboards."""
from __future__ import annotations

from datetime import timezone
from typing import Dict

import pandas as pd


def _to_utc(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce")


def compute_kpis(segments: pd.DataFrame, entries: pd.DataFrame) -> Dict[str, object]:
    segments = segments.copy()
    entries = entries.copy()
    entries["timestamp"] = _to_utc(entries.get("timestamp", pd.Series(dtype=str)))

    today = pd.Timestamp.now(tz=timezone.utc).normalize()
    complete_events = entries[entries["action"].str.title() == "Complete"].copy()
    complete_events = complete_events.dropna(subset=["timestamp"])

    segments_today = 0
    if not complete_events.empty:
        latest_per_segment = (
            complete_events.sort_values("timestamp")
            .groupby(["seam_id", "segment_no"], as_index=False)
            .tail(1)
        )
        segments_today = int(
            (latest_per_segment["timestamp"].dt.normalize() == today).sum()
        )

    wip_segments = int((segments["segment_status"] == "In progress").sum())
    complete_segments = segments[segments["segment_status"] == "Complete"]

    cycle_time_hours = 0.0
    if not entries.empty and not complete_segments.empty:
        # compute cycle time per segment (first start to last complete)
        starts = (
            entries[entries["action"].str.title() == "Start"]
            .sort_values("timestamp")
            .groupby(["seam_id", "segment_no"], as_index=False)
            .head(1)
        )
        completes = (
            complete_events.sort_values("timestamp")
            .groupby(["seam_id", "segment_no"], as_index=False)
            .tail(1)
        )
        merged = starts.merge(
            completes,
            on=["seam_id", "segment_no"],
            suffixes=("_start", "_complete"),
        )
        if not merged.empty:
            durations = (
                merged["timestamp_complete"] - merged["timestamp_start"]
            ).dt.total_seconds() / 3600.0
            durations = durations[durations >= 0]
            if not durations.empty:
                cycle_time_hours = float(durations.mean())

    throughput_shift = (
        complete_events.groupby(complete_events["shift"].fillna("Unspecified")).size()
        if not complete_events.empty
        else pd.Series(dtype=int)
    )

    return {
        "segments_completed_today": segments_today,
        "wip_segments": wip_segments,
        "average_cycle_hours": cycle_time_hours,
        "throughput_by_shift": throughput_shift.to_dict(),
    }


def build_progress_by_pass(entries: pd.DataFrame) -> pd.DataFrame:
    entries = entries.copy()
    entries["timestamp"] = _to_utc(entries.get("timestamp", pd.Series(dtype=str)))
    entries = entries.dropna(subset=["timestamp"])
    if entries.empty:
        return pd.DataFrame(columns=["date", "pass", "completions"])

    completes = entries[entries["action"].str.title() == "Complete"]
    if completes.empty:
        return pd.DataFrame(columns=["date", "pass", "completions"])

    completes["date"] = completes["timestamp"].dt.date
    grouped = (
        completes.groupby(["date", "pass"], as_index=False)["timestamp"].count()
    )
    grouped = grouped.rename(columns={"timestamp": "completions"})
    return grouped


__all__ = ["compute_kpis", "build_progress_by_pass"]
