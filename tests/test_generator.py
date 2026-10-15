import numpy as np
import pandas as pd

from core.schema import (BOOKING_COLS, BOOKING_STATUSES, ID_REGEX, MAX_DURATION_MIN,
                         MIN_DURATION_MIN, SESSION_COLS)
from data.generate_data import simulate


def test_same_seed_gives_identical_data():
    a = simulate(seed=3, n_days=6, n_drivers=30, base_requests=4)
    b = simulate(seed=3, n_days=6, n_drivers=30, base_requests=4)
    pd.testing.assert_frame_equal(a["bookings"], b["bookings"])


def test_different_seed_changes_data():
    a = simulate(seed=3, n_days=6, n_drivers=30, base_requests=4)
    b = simulate(seed=4, n_days=6, n_drivers=30, base_requests=4)
    assert not a["bookings"].equals(b["bookings"])


def test_columns_and_ids(small):
    b, s = small["bookings"], small["sessions"]
    assert list(b.columns) == BOOKING_COLS and list(s.columns) == SESSION_COLS
    assert b["booking_id"].map(lambda x: bool(ID_REGEX["booking"].match(x))).all()
    assert b["booking_id"].is_unique and s["session_id"].is_unique
    assert set(b["status"]) <= set(BOOKING_STATUSES)


def test_durations_in_range_and_end_matches(small):
    b = small["bookings"]
    assert b["duration_min"].between(MIN_DURATION_MIN, MAX_DURATION_MIN).all()
    assert ((b["end_time"] - b["start_time"]) == pd.to_timedelta(b["duration_min"], unit="m")).all()


def test_no_overlapping_bookings_on_same_charger(small):
    """Core scheduling invariant: A.start < B.end and B.start < A.end must never hold."""
    b = small["bookings"]
    active = b[b["status"].isin(["Completed", "No-Show"])].sort_values(["charger_id", "start_time"])
    for _, g in active.groupby("charger_id"):
        starts, ends = g["start_time"].to_numpy(), g["end_time"].to_numpy()
        assert (starts[1:] >= ends[:-1]).all()


def test_sessions_only_for_completed_and_consistent(small):
    b, s = small["bookings"], small["sessions"]
    done = set(b.loc[b["status"] == "Completed", "booking_id"])
    assert set(s["booking_id"]) == done
    assert (s["delay_min"] >= 0).all() and (s["energy_kwh"] > 0).all()
    assert (s["actual_start"] >= s["planned_start"]).all()


def test_maintenance_chargers_never_booked(small):
    maint = set(small["chargers"].query("status == 'Maintenance'")["charger_id"])
    assert maint and not (set(small["bookings"]["charger_id"].dropna()) & maint)


def test_charger_connector_matches_booking(small):
    m = small["bookings"].dropna(subset=["charger_id"]).merge(
        small["chargers"][["charger_id", "connector"]], on="charger_id", suffixes=("", "_ch"))
    assert (m["connector"] == m["connector_ch"]).all()


def test_realistic_patterns(small):
    b = small["bookings"]
    hours = b["start_time"].dt.hour.value_counts()
    assert hours.idxmax() in (8, 9, 17, 18, 19)                 # rush hours dominate
    assert hours.get(3, 0) < hours.max() * 0.2                  # night is quiet
