"""Status computation utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

import pandas as pd


@dataclass(frozen=True)
class EntryRecord:
    seam_id: str
    segment_no: int
    pass_name: str
    action: str
    timestamp: pd.Timestamp
    welder_id: str


def _normalize_pass(value: str) -> str:
    return value.strip()


def _normalize_action(value: str) -> str:
    return value.strip().title()


def _latest_complete(entries: pd.DataFrame) -> Dict[Tuple[str, int, str], EntryRecord]:
    complete = entries[entries["action_norm"] == "Complete"]
    if complete.empty:
        return {}
    idx = (
        complete.sort_values("timestamp")
        .groupby(["seam_id", "segment_no", "pass_norm"], as_index=False)
        .tail(1)
    )
    records: Dict[Tuple[str, int, str], EntryRecord] = {}
    for row in idx.itertuples():
        records[(row.seam_id, int(row.segment_no), row.pass_norm)] = EntryRecord(
            seam_id=row.seam_id,
            segment_no=int(row.segment_no),
            pass_name=row.pass_norm,
            action=row.action_norm,
            timestamp=row.timestamp,
            welder_id=row.welder_id,
        )
    return records


def _start_keys(entries: pd.DataFrame) -> set[Tuple[str, int, str]]:
    starts = entries[entries["action_norm"] == "Start"]
    if starts.empty:
        return set()
    return {
        (row.seam_id, int(row.segment_no), row.pass_norm)
        for row in starts.itertuples()
    }


def compute_segment_status(
    segments: pd.DataFrame,
    entries: pd.DataFrame,
) -> pd.DataFrame:
    segments = segments.copy()
    segments = segments.drop(
        columns=[
            "segment_status",
            "percent_complete",
            "root_by",
            "root_at",
            "fill_by",
            "fill_at",
            "cap_by",
            "cap_at",
        ],
        errors="ignore",
    )
    if segments.empty:
        for column in [
            "segment_status",
            "percent_complete",
            "root_by",
            "root_at",
            "fill_by",
            "fill_at",
            "cap_by",
            "cap_at",
        ]:
            segments[column] = []
        return segments

    entries = entries.copy()
    if entries.empty:
        entries = pd.DataFrame(columns=[
            "seam_id",
            "segment_no",
            "pass",
            "action",
            "timestamp",
            "welder_id",
        ])

    entries["timestamp"] = pd.to_datetime(entries["timestamp"], utc=True, errors="coerce")
    entries = entries.dropna(subset=["timestamp"])
    entries["pass_norm"] = entries["pass"].astype(str).map(_normalize_pass)
    entries["action_norm"] = entries["action"].astype(str).map(_normalize_action)

    latest = _latest_complete(entries)
    starts = _start_keys(entries)

    derived_rows = []
    for seg in segments.itertuples():
        passes = [p.strip() for p in str(seg.pass_list).split("|") if p.strip()]
        total = len(passes)
        done = 0
        status = "Not started"
        root_by = root_at = fill_by = fill_at = cap_by = cap_at = None

        for pass_name in passes:
            key = (seg.seam_id, int(seg.segment_no), pass_name)
            complete_record = latest.get(key)
            if complete_record:
                done += 1
                status = "In progress" if done < total else "Complete"
                ts_str = complete_record.timestamp.isoformat()
                if pass_name.lower() == "root":
                    root_by, root_at = complete_record.welder_id, ts_str
                if pass_name.lower() == "fill":
                    fill_by, fill_at = complete_record.welder_id, ts_str
                if pass_name.lower() == "cap":
                    cap_by, cap_at = complete_record.welder_id, ts_str
            elif key in starts:
                status = "In progress"

        if total == 0:
            percent = 0.0
        else:
            percent = done / total
            if percent == 0 and status == "In progress":
                percent = 0.0

        if done == 0 and status != "In progress":
            status = "Not started"
        elif done == total and total > 0:
            status = "Complete"

        derived_rows.append(
            {
                "seam_id": seg.seam_id,
                "segment_no": int(seg.segment_no),
                "segment_status": status,
                "percent_complete": percent,
                "root_by": root_by,
                "root_at": root_at,
                "fill_by": fill_by,
                "fill_at": fill_at,
                "cap_by": cap_by,
                "cap_at": cap_at,
            }
        )

    derived_df = pd.DataFrame(derived_rows)
    merged = segments.merge(derived_df, on=["seam_id", "segment_no"], how="left")
    return merged


__all__ = ["compute_segment_status", "EntryRecord"]
