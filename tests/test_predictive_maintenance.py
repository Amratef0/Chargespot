import numpy as np
import pandas as pd
import pytest

from ai.predictive_maintenance import (MaintenanceError, assess_chargers, evaluate_against_truth,
                                       inspection_list)
from data.generate_data import build_chargers, load_catalog, simulate_charger_health


def health_for(seed):
    ch = build_chargers(load_catalog())
    h, t = simulate_charger_health(ch, 120, "2026-03-31", seed)
    return h, t, ch


def test_manual_hand_calculation_power_only():
    days = pd.date_range("2026-01-01", periods=60)
    power = [0.97] * 46 + [0.87] * 14                      # recent 14 days lose exactly 10 pp
    h = pd.DataFrame({"charger_id": "CH001", "date": days, "power_ratio": power,
                      "error_count": 0, "temp_c": 38.0})
    a = assess_chargers(h).iloc[0]
    assert a["power_drop_pp"] == pytest.approx(10.0) and a["risk_score"] == 40.0
    assert a["risk_level"] == "Medium" and "power output down" in a["reasons"]


def test_flat_charger_has_zero_risk():
    days = pd.date_range("2026-01-01", periods=60)
    h = pd.DataFrame({"charger_id": "CH001", "date": days, "power_ratio": 0.97, "error_count": 1, "temp_c": 40.0})
    a = assess_chargers(h).iloc[0]
    assert a["risk_score"] == 0 and a["risk_level"] == "Low"


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5, 6])
def test_strongly_degrading_chargers_are_always_caught(seed):
    h, truth, ch = health_for(seed)
    a = assess_chargers(h, ch).merge(truth, on="charger_id")
    degr = a[a["true_class"] == "degrading"]
    assert len(degr) == 3 and degr["risk_level"].isin(["High", "Medium"]).all()


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5, 6])
def test_stable_noisy_chargers_are_not_flagged_high(seed):
    h, truth, ch = health_for(seed)
    a = assess_chargers(h, ch).merge(truth, on="charger_id")
    assert not (a[a["true_class"] == "stable_noisy"]["risk_level"] == "High").any()


def test_few_false_alarms_on_generated_fleet():
    h, truth, ch = health_for(42)
    ev = evaluate_against_truth(assess_chargers(h, ch), truth)
    assert ev["recall"] == 1.0 and ev["false_positives"] <= 1


def test_inspection_list_only_contains_flagged_chargers():
    h, _, ch = health_for(42)
    insp = inspection_list(assess_chargers(h, ch))
    assert set(insp["risk_level"]) <= {"High", "Medium"} and len(insp) >= 3


def test_insufficient_history_is_reported_not_crashing():
    h = pd.DataFrame({"charger_id": "CH001", "date": pd.date_range("2026-03-01", periods=10),
                      "power_ratio": 0.9, "error_count": 0, "temp_c": 38.0})
    a = assess_chargers(h).iloc[0]
    assert a["risk_level"] == "Insufficient data" and np.isnan(a["risk_score"])


def test_nan_readings_are_tolerated():
    h, _, ch = health_for(42)
    h.loc[h.sample(300, random_state=1).index, "power_ratio"] = np.nan
    assert "risk_level" in assess_chargers(h, ch).columns


def test_missing_columns_and_empty_raise_friendly_error():
    with pytest.raises(MaintenanceError, match="temp_c"):
        assess_chargers(pd.DataFrame({"charger_id": ["A"], "date": [pd.Timestamp("2026-01-01")],
                                      "power_ratio": [1], "error_count": [0]}))
    with pytest.raises(MaintenanceError):
        assess_chargers(pd.DataFrame(columns=["charger_id", "date", "power_ratio", "error_count", "temp_c"]))


def test_health_generation_is_deterministic_and_maintenance_chargers_excluded():
    h1, t1, ch = health_for(9)
    h2, t2, _ = health_for(9)
    pd.testing.assert_frame_equal(h1, h2)
    maint = set(ch.loc[ch["status"] == "Maintenance", "charger_id"])
    assert maint and not (set(h1["charger_id"]) & maint)
