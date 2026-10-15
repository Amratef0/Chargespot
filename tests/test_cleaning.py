import numpy as np
import pandas as pd
import pytest

from analytics.cleaning import (CleaningError, clean_bookings, compare_with_manifest,
                                parse_datetime)
from core.schema import BOOKING_COLS


def test_every_injected_defect_is_detected_exactly(small, messy):
    df, manifest = messy
    clean, rep = clean_bookings(df, small["stations"])
    cmp_df = compare_with_manifest(rep, manifest)
    assert cmp_df["match"].all(), cmp_df.to_string()


def test_rows_add_up(small, messy):
    df, _ = messy
    clean, rep = clean_bookings(df, small["stations"])
    assert rep.rows_before == len(df) and rep.rows_after == len(clean)
    assert rep.rows_before - sum(rep.dropped.values()) == rep.rows_after


def test_clean_output_is_valid(small, messy):
    clean, _ = clean_bookings(messy[0], small["stations"])
    assert clean["booking_id"].is_unique
    assert clean["start_time"].notna().all()
    assert clean["duration_min"].between(15, 240).all()
    assert set(clean["connector"]) <= {"CCS2", "CHAdeMO", "Type 2"}
    assert set(clean["status"]) <= {"Completed", "No-Show", "Cancelled", "Waiting", "Confirmed"}
    assert ((clean["end_time"] - clean["start_time"]) == pd.to_timedelta(clean["duration_min"], unit="m")).all()
    assert clean["wait_min"].notna().all()


def test_cleaning_is_idempotent(small, messy):
    once, _ = clean_bookings(messy[0], small["stations"])
    raw_again = once.copy()
    for c in ("created_at", "start_time", "end_time"):
        raw_again[c] = raw_again[c].dt.strftime("%Y-%m-%d %H:%M")
    twice, rep2 = clean_bookings(raw_again, small["stations"])
    assert rep2.rows_removed == 0 and rep2.fixed == {}
    assert len(twice) == len(once)


def test_already_clean_data_has_no_defects(small):
    b = small["bookings"].copy()
    for c in ("created_at", "start_time", "end_time"):
        b[c] = b[c].dt.strftime("%Y-%m-%d %H:%M")
    _, rep = clean_bookings(b, small["stations"])
    assert rep.dropped == {} and rep.fixed == {}


def test_missing_columns_raise_friendly_error():
    with pytest.raises(CleaningError, match="start_time"):
        clean_bookings(pd.DataFrame({"booking_id": ["1"]}))


def test_empty_dataframe_does_not_crash():
    clean, rep = clean_bookings(pd.DataFrame(columns=BOOKING_COLS))
    assert clean.empty and rep.rows_before == 0


def test_garbage_values_are_dropped_not_crashing():
    raw = pd.DataFrame([{
        "booking_id": "1", "driver_id": "D101", "station_id": "1", "charger_id": "AC-101",
        "connector": "CCS", "created_at": "x", "start_time": "tomorrow-ish", "end_time": "???",
        "duration_min": "abc", "status": "Completed", "queued": "no", "wait_min": "n/a"}])
    clean, rep = clean_bookings(raw)
    assert clean.empty and rep.dropped["missing_or_invalid_start_time"] == 1


def test_unrepairable_duration_is_dropped():
    raw = pd.DataFrame([{
        "booking_id": "1", "driver_id": "D101", "station_id": "1", "charger_id": "AC-101",
        "connector": "CCS", "created_at": "2026-01-01 08:00", "start_time": "2026-01-01 10:00",
        "end_time": None, "duration_min": "-5", "status": "Completed", "queued": "0", "wait_min": "0"}])
    clean, rep = clean_bookings(raw)
    assert clean.empty and rep.dropped["unrepairable_duration"] == 1


def test_queued_cancelled_row_without_charger_is_kept():
    raw = pd.DataFrame([{
        "booking_id": "1", "driver_id": "D101", "station_id": "1", "charger_id": None,
        "connector": "ccs", "created_at": "2026-01-01 08:00", "start_time": "2026-01-01 10:00",
        "end_time": "2026-01-01 11:00", "duration_min": "60", "status": "canceled", "queued": "1",
        "wait_min": "25"}])
    clean, rep = clean_bookings(raw)
    assert len(clean) == 1 and clean.loc[0, "status"] == "Cancelled" and clean.loc[0, "connector"] == "CCS2"


@pytest.mark.parametrize("text", ["2026-03-31 10:15", "2026-03-31T10:15", "31/03/2026 10:15", "Mar 31 2026 10:15"])
def test_all_date_formats_parse_to_same_timestamp(text):
    assert parse_datetime(pd.Series([text])).iloc[0] == pd.Timestamp("2026-03-31 10:15")


def test_unparseable_date_is_nat():
    assert parse_datetime(pd.Series(["not a date", None])).isna().all()
