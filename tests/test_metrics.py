import pandas as pd
import pytest

from analytics import metrics as M
from analytics.insights import generate_insights
from tests.conftest import mk_bookings


def test_rates_use_decided_bookings_only():
    b = mk_bookings([
        ("BK00001", "ST01", "2026-01-05 08:00", 60, "Completed", 0, 0),
        ("BK00002", "ST01", "2026-01-05 09:00", 60, "Completed", 0, 0),
        ("BK00003", "ST01", "2026-01-05 10:00", 60, "Cancelled", 0, 0),
        ("BK00004", "ST01", "2026-01-05 11:00", 60, "No-Show", 0, 0),
        ("BK00005", "ST01", "2026-01-06 11:00", 60, "Confirmed", 0, 0),     # not decided
    ])
    assert M.completion_rate(b) == 50.0
    assert M.cancellation_rate(b) == 25.0
    assert M.no_show_rate(b) == 25.0


def test_peak_hour_and_tie_breaks_to_earliest():
    b = mk_bookings([("BK00001", "ST01", "2026-01-05 18:00", 60, "Completed", 0, 0),
                     ("BK00002", "ST01", "2026-01-05 18:30", 60, "Completed", 0, 0),
                     ("BK00003", "ST01", "2026-01-05 08:00", 60, "Completed", 0, 0),
                     ("BK00004", "ST01", "2026-01-05 08:15", 60, "Completed", 0, 0)])
    assert M.peak_hour(b) == 8


def test_waiting_stats_average_only_over_queued():
    b = mk_bookings([("BK00001", "ST01", "2026-01-05 08:00", 60, "Completed", 1, 20),
                     ("BK00002", "ST01", "2026-01-05 09:00", 60, "Completed", 1, 40),
                     ("BK00003", "ST01", "2026-01-05 10:00", 60, "Completed", 0, 0)])
    w = M.waiting_stats(b)
    assert w["avg_wait_min"] == 30.0 and w["queued_bookings"] == 2 and w["max_wait_min"] == 40


def test_utilization_hand_calculation():
    stations = pd.DataFrame({"station_id": ["ST01"], "name": ["A"], "city": ["X"],
                             "open_hour": [8], "close_hour": [18]})          # 10 h open
    chargers = pd.DataFrame({"charger_id": ["CH001", "CH002", "CH003"], "station_id": ["ST01"] * 3,
                             "status": ["Available", "Occupied", "Maintenance"]})   # 2 active
    sessions = pd.DataFrame({"session_id": ["SS00001", "SS00002"], "station_id": ["ST01"] * 2,
                             "actual_start": pd.to_datetime(["2026-01-05 09:00", "2026-01-06 09:00"]),
                             "duration_min": [120, 120], "delay_min": [0, 0],
                             "energy_kwh": [10.0, 10.0], "cost_egp": [50.0, 50.0]})
    u = M.station_utilization(sessions, chargers, stations, "2026-01-05", "2026-01-06")
    # capacity = 2 chargers * 600 min * 2 days = 2400 ; busy = 240 -> 10 %
    assert u.loc[0, "capacity_min"] == 2400 and u.loc[0, "utilization_pct"] == 10.0


def test_utilization_never_exceeds_100():
    stations = pd.DataFrame({"station_id": ["ST01"], "name": ["A"], "city": ["X"], "open_hour": [8], "close_hour": [9]})
    chargers = pd.DataFrame({"charger_id": ["CH001"], "station_id": ["ST01"], "status": ["Available"]})
    sessions = pd.DataFrame({"session_id": ["SS00001"], "station_id": ["ST01"],
                             "actual_start": pd.to_datetime(["2026-01-05 08:00"]), "duration_min": [500],
                             "delay_min": [0], "energy_kwh": [1.0], "cost_egp": [1.0]})
    assert M.station_utilization(sessions, chargers, stations, "2026-01-05", "2026-01-05").loc[0, "utilization_pct"] == 100.0


def test_daily_demand_fills_gaps_with_zero():
    b = mk_bookings([("BK00001", "ST01", "2026-01-01 08:00", 60, "Completed", 0, 0),
                     ("BK00002", "ST01", "2026-01-04 08:00", 60, "Completed", 0, 0)])
    d = M.daily_demand(b)
    assert len(d) == 4 and list(d["bookings"]) == [1, 0, 0, 1]


def test_heatmap_shape_always_7x24():
    b = mk_bookings([("BK00001", "ST01", "2026-01-05 08:00", 60, "Completed", 0, 0)])
    assert M.demand_heatmap(b).shape == (7, 24)


def test_empty_inputs_do_not_crash(small):
    b, s = small["bookings"].iloc[0:0], small["sessions"].iloc[0:0]
    k = M.kpi_summary(b, s, small["chargers"], small["stations"])
    assert k["total_bookings"] == 0 and k["peak_hour"] is None
    assert M.demand_by_weekday(b)["bookings"].sum() == 0
    assert generate_insights(b, s, small["stations"], small["chargers"])[0].title == "No data"


def test_filter_period_is_inclusive_and_consistent(small):
    b, s = small["bookings"], small["sessions"]
    fb, fs = M.filter_period(b, s, "2026-02-10", "2026-02-10", ["9"], ["CCS2"])
    assert (fb["start_time"].dt.date.astype(str) == "2026-02-10").all()
    assert set(fb["station_id"]) <= {"9"} and set(fb["connector"]) <= {"CCS2"}
    assert set(fs["booking_id"]) <= set(fb["booking_id"])


def test_insights_are_generated_from_data_not_hardcoded(small):
    st_, ch = small["stations"], small["chargers"]
    full = generate_insights(small["bookings"], small["sessions"], st_, ch)
    only = small["bookings"][small["bookings"]["station_id"] == "9"]
    one = generate_insights(only, small["sessions"][small["sessions"]["station_id"] == "9"], st_, ch)
    assert full[0].text != one[0].text
    peak = M.peak_hour(small["bookings"])
    assert f"{peak:02d}:00" in full[0].text
