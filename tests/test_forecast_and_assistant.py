import pandas as pd
import pytest

from ai.analytics_assistant import AnalyticsAssistant
from ai.forecast import ForecastError, forecast_demand
from analytics import metrics as M


def test_forecast_needs_enough_history(small):
    short = small["bookings"][small["bookings"]["start_time"] < "2026-02-10"]
    with pytest.raises(ForecastError, match="at least"):
        forecast_demand(short)


def test_forecast_empty_raises_friendly_error(small):
    with pytest.raises(ForecastError):
        forecast_demand(small["bookings"].iloc[0:0])


def test_forecast_holdout_has_no_leakage_and_outputs_valid(small):
    b = small["bookings"]
    r = forecast_demand(b, test_days=7)
    last = b["start_time"].dt.normalize().max()
    assert r.test_predictions["ts"].min() >= last - pd.Timedelta(days=6)
    assert (r.future["ts"] > last).all() and (r.future["predicted_bookings"] >= 0).all()
    assert len(r.metrics) == 3 and (r.metrics["MAE"] > 0).all()
    assert r.future["ts"].dt.normalize().nunique() == 7


def test_assistant_answers_match_computed_metrics(small):
    a = AnalyticsAssistant(small["bookings"], small["sessions"], small["stations"], small["chargers"])
    peak = M.peak_hour(small["bookings"])
    assert f"{peak:02d}:00" in a.ask("When is the peak hour?")
    assert f"{M.cancellation_rate(small['bookings']):.1f}%" in a.ask("cancellation rate?")
    assert f"{peak:02d}:00" in a.ask("ايه ساعة الذروة؟")                     # Arabic


def test_assistant_unknown_question_and_empty_data(small):
    a = AnalyticsAssistant(small["bookings"], small["sessions"], small["stations"], small["chargers"])
    assert "I can answer" in a.ask("what is the weather?")
    e = AnalyticsAssistant(small["bookings"].iloc[0:0], small["sessions"].iloc[0:0], small["stations"], small["chargers"])
    assert "no data" in e.ask("peak").lower()
