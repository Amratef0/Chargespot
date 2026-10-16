"""Cleaning pipeline for booking data (Member 4).

    clean_df, report = clean_bookings(raw_df, stations=stations_df)

* works on ANY booking CSV that follows core/schema.py (so it also works with
changed data / an uploaded file)
* never crashes on bad values: every bad row is either REPAIRED (counted in
report.fixed) or DROPPED (counted in report.dropped, with the reason)
* the report is the "cleaning evidence" for the submission
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from core.schema import (BOOKING_COLS, DATETIME_FORMAT, ID_REGEX,
                        MAX_DURATION_MIN, MIN_DURATION_MIN,
                        REQUIRED_BOOKING_COLS)

STATUS_ALIASES = {
    "confirmed": "Confirmed", "waiting": "Waiting", "completed": "Completed",
    "complete": "Completed", "done": "Completed", "cancelled": "Cancelled",
    "canceled": "Cancelled", "cancel": "Cancelled", "no-show": "No-Show",
    "no show": "No-Show", "noshow": "No-Show", "no_show": "No-Show",
}
CONNECTOR_ALIASES = {
    "ccs": "CCS2", "ccs2": "CCS2", "combo": "CCS2", "chademo": "CHAdeMO",
    "type2": "Type 2", "type 2": "Type 2", "type-2": "Type 2", "mennekes": "Type 2",
}
DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M", "%d-%m-%Y %H:%M", "%b %d %Y %H:%M",
)
_STANDARD_DT = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$"


class CleaningError(ValueError):
    """Raised when a file cannot be cleaned at all (e.g. missing columns)."""


@dataclass
class CleaningReport:
    rows_before: int = 0
    rows_after: int = 0
    dropped: dict = field(default_factory=dict)   # reason -> rows removed
    fixed: dict = field(default_factory=dict)     # fix   -> rows repaired

    @property
    def rows_removed(self) -> int:
        return self.rows_before - self.rows_after

    @property
    def retention_pct(self) -> float:
        return 100.0 * self.rows_after / self.rows_before if self.rows_before else 0.0

    def to_frame(self) -> pd.DataFrame:
        rows = [("dropped", k, v) for k, v in self.dropped.items()]
        rows += [("fixed", k, v) for k, v in self.fixed.items()]
        return pd.DataFrame(rows, columns=["action", "defect", "rows"])


def parse_datetime(series: pd.Series) -> pd.Series:
    """Parse strings in several known formats; anything else becomes NaT."""
    s = series.astype("string").str.strip()
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    for fmt in DATETIME_FORMATS:
        pending = out.isna() & s.notna()
        if not pending.any():
            break
        parsed = pd.to_datetime(s[pending], format=fmt, errors="coerce")
        out.loc[pending] = parsed.astype("datetime64[ns]")
    return out


def _drop(df, mask, reason, log):
    mask = pd.Series(mask, index=df.index).fillna(False).astype(bool)
    n = int(mask.sum())
    if n:
        log[reason] = log.get(reason, 0) + n
    return df.loc[~mask]


def _count(mask) -> int:
    return int(pd.Series(mask).fillna(False).astype(bool).sum())


def clean_bookings(raw: pd.DataFrame, stations: pd.DataFrame | None = None):
    """Clean a bookings DataFrame. Returns (clean_df, CleaningReport)."""
    missing = [c for c in REQUIRED_BOOKING_COLS if c not in raw.columns]
    if missing:
        raise CleaningError(f"Missing required column(s): {', '.join(missing)}")

    rpt = CleaningReport(rows_before=len(raw))
    drop, fix = rpt.dropped, rpt.fixed

    df = raw.copy()
    orig = {c: raw[c].astype("string") for c in ("status", "connector")}   # before trimming
    for c in BOOKING_COLS:                      # optional columns -> create empty
        if c not in df.columns:
            df[c] = pd.NA
    df = df[BOOKING_COLS]
    for c in df.columns:                        # everything to trimmed strings first
        df[c] = df[c].astype("string").str.strip().replace("", pd.NA)

    # 1. IDs ---------------------------------------------------------------
    df = _drop(df, ~df["booking_id"].str.match(ID_REGEX["booking"].pattern).fillna(False),
            "invalid_booking_id", drop)
    df = _drop(df, df["booking_id"].duplicated(keep="first"), "duplicate_booking_id", drop)
    df = _drop(df, ~df["station_id"].str.match(ID_REGEX["station"].pattern).fillna(False),
            "invalid_station_id", drop)
    if stations is not None:
        df = _drop(df, ~df["station_id"].isin(set(stations["station_id"])), "unknown_station", drop)

    # 2. timestamps --------------------------------------------------------
    start = parse_datetime(df["start_time"])
    df = _drop(df, start.isna(), "missing_or_invalid_start_time", drop)
    start = start.loc[df.index]
    nonstd = ~df["start_time"].str.match(_STANDARD_DT).fillna(False)
    if _count(nonstd):
        fix["datetime_format_normalized"] = _count(nonstd)
    end = parse_datetime(df["end_time"])
    created = parse_datetime(df["created_at"])

    # 3. categorical normalisation ----------------------------------------
    status = df["status"].str.lower().map(STATUS_ALIASES)
    changed = status.notna() & (status != orig["status"].loc[df.index])
    if _count(changed):
        fix["status_normalized"] = _count(changed)
    df["status"] = status
    df = _drop(df, df["status"].isna(), "unknown_status", drop)

    conn = df["connector"].str.lower().map(CONNECTOR_ALIASES)
    changed = conn.notna() & (conn != orig["connector"].loc[df.index])
    if _count(changed):
        fix["connector_normalized"] = _count(changed)
    df["connector"] = conn
    df = _drop(df, df["connector"].isna(), "unknown_connector", drop)

    # 4. charger id --------------------------------------------------------
    bad_fmt = df["charger_id"].notna() & ~df["charger_id"].str.match(ID_REGEX["charger"].pattern).fillna(False)
    df = _drop(df, bad_fmt, "invalid_charger_id", drop)
    no_charger_ok = df["status"].isin(["Waiting", "Cancelled"])     # queued requests have no charger
    df = _drop(df, df["charger_id"].isna() & ~no_charger_ok, "missing_charger_id", drop)

    # 5. duration ----------------------------------------------------------
    start, end, created = start.loc[df.index], end.loc[df.index], created.loc[df.index]
    dur = pd.to_numeric(df["duration_min"], errors="coerce")
    bad_dur = dur.isna() | (dur < MIN_DURATION_MIN) | (dur > MAX_DURATION_MIN)
    from_ts = ((end - start).dt.total_seconds() / 60).round()
    repairable = bad_dur & from_ts.between(MIN_DURATION_MIN, MAX_DURATION_MIN)
    if _count(repairable):
        fix["invalid_duration_repaired"] = _count(repairable)
    dur = dur.where(~repairable, from_ts)
    keep = ~(bad_dur & ~repairable)
    df = _drop(df, ~keep, "unrepairable_duration", drop)
    dur, start, end, created = (x.loc[df.index] for x in (dur, start, end, created))

    # 6. end time must equal start + duration ------------------------------
    ebs = end.notna() & (end <= start)
    if _count(ebs & ~repairable.loc[df.index]):
        fix["end_before_start_recomputed"] = _count(ebs & ~repairable.loc[df.index])
    new_end = start + pd.to_timedelta(dur, unit="m")

    # 7. fill missing values ----------------------------------------------
    wait = pd.to_numeric(df["wait_min"], errors="coerce")
    if _count(wait.isna()):
        fix["wait_min_filled_with_0"] = _count(wait.isna())
    queued = pd.to_numeric(df["queued"], errors="coerce")
    queued = queued.fillna((wait.fillna(0) > 0).astype(int))
    if _count(created.isna()):
        fix["created_at_filled_with_start"] = _count(created.isna())

    out = pd.DataFrame({
        "booking_id": df["booking_id"].astype(object),
        "driver_id": df["driver_id"].astype(object),
        "station_id": df["station_id"].astype(object),
        "charger_id": df["charger_id"].astype(object),
        "connector": df["connector"].astype(object),
        "created_at": created.fillna(start),
        "start_time": start,
        "end_time": new_end,
        "duration_min": dur.astype(int),
        "status": df["status"].astype(object),
        "queued": queued.astype(int),
        "wait_min": wait.fillna(0).round().astype(int),
    })
    out = out.sort_values("start_time", kind="mergesort").reset_index(drop=True)
    rpt.rows_after = len(out)
    return out, rpt


def load_clean_bookings(path, stations: pd.DataFrame | None = None):
    """Read a CSV as raw strings and clean it."""
    raw = pd.read_csv(path, dtype=str, keep_default_na=True)
    return clean_bookings(raw, stations)


# injected defect (data/generate_data.py manifest)  ->  how the cleaner reports it
MANIFEST_TO_DEFECT = {
    "duplicate_rows": "duplicate_booking_id",
    "mixed_date_formats": "datetime_format_normalized",
    "missing_start_time": "missing_or_invalid_start_time",
    "invalid_duration": "invalid_duration_repaired",
    "connector_variants": "connector_normalized",
    "status_variants": "status_normalized",
    "invalid_booking_id": "invalid_booking_id",
    "missing_charger_id": "missing_charger_id",
    "end_before_start": "end_before_start_recomputed",
    "missing_wait_min": "wait_min_filled_with_0",
    "unknown_station": "unknown_station",
}


def compare_with_manifest(report: CleaningReport, injected: dict) -> pd.DataFrame:
    """Evidence table: defects injected into the messy file vs defects detected."""
    found = {**report.dropped, **report.fixed}
    rows = []
    for kind, n in injected.items():
        key = MANIFEST_TO_DEFECT.get(kind, kind)
        rows.append({"injected_defect": kind, "reported_as": key, "injected": n,
                    "detected": found.get(key, 0), "match": found.get(key, 0) == n})
    return pd.DataFrame(rows)
