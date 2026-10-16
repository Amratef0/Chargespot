"""Charging-demand prediction (optional AI feature, Member 4).

Predicts how many bookings start at each station in each hour, 1-7 days ahead.

Honest evaluation (important for the defense):
  * HOLD-OUT: the last `test_days` of history are never used for training.
  * BASELINE: average bookings for the same (station, weekday, hour) in the
    training period. The ML model must beat this to be worth anything.
  * Data is SYNTHETIC, so the accuracy only shows the pipeline works - it does
    not prove real-world accuracy.

Features (all known `horizon_days` ahead, so there is no data leakage):
    hour (cyclical), weekday, is_weekend (Fri/Sat), station,
    same-hour demand 7 days earlier (lag_7),
    station's average daily demand during the 7 days ending 7 days earlier.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance

from core.schema import WEEKEND_DAYS

HORIZON_DAYS = 7
MIN_HISTORY_DAYS = 28


class ForecastError(ValueError):
    """Raised with a friendly message when a forecast cannot be built."""


@dataclass
class ForecastResult:
    metrics: pd.DataFrame                  # MAE / RMSE: naive vs baseline vs model
    test_predictions: pd.DataFrame         # station_id, ts, actual, baseline, model
    future: pd.DataFrame                   # station_id, ts, predicted_bookings
    importances: pd.DataFrame              # feature, importance
    test_days: int = 14
    note: str = ("Synthetic data: accuracy shows the pipeline works, "
                "not real-world performance.")


def _panel(bookings: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Complete station x day x hour grid with counts (NaN for future days)."""
    b = bookings.copy()
    b["date"] = b["start_time"].dt.normalize()
    b["hour"] = b["start_time"].dt.hour
    counts = b.groupby(["station_id", "date", "hour"]).size().rename("count")
    first, last = b["date"].min(), b["date"].max()
    dates = pd.date_range(first, last + pd.Timedelta(days=horizon), freq="D")
    idx = pd.MultiIndex.from_product([sorted(b["station_id"].unique()), dates, range(24)],
                                    names=["station_id", "date", "hour"])
    p = counts.reindex(idx).reset_index()
    p.loc[p["date"] <= last, "count"] = p.loc[p["date"] <= last, "count"].fillna(0)
    return p, last


def _features(p: pd.DataFrame) -> pd.DataFrame:
    p = p.sort_values(["station_id", "hour", "date"]).copy()
    p["lag_7"] = p.groupby(["station_id", "hour"])["count"].shift(7)
    daily = p.groupby(["station_id", "date"])["count"].sum(min_count=1).rename("daily").reset_index()
    daily = daily.sort_values(["station_id", "date"])
    daily["roll7"] = (daily.groupby("station_id")["daily"]
                    .transform(lambda s: s.shift(7).rolling(7, min_periods=7).mean()))
    p = p.merge(daily[["station_id", "date", "roll7"]], on=["station_id", "date"], how="left")
    p["weekday"] = p["date"].dt.weekday
    p["is_weekend"] = p["weekday"].isin(WEEKEND_DAYS).astype(int)
    p["hour_sin"] = np.sin(2 * np.pi * p["hour"] / 24)
    p["hour_cos"] = np.cos(2 * np.pi * p["hour"] / 24)
    return p.sort_values(["station_id", "date", "hour"]).reset_index(drop=True)


def _matrix(p: pd.DataFrame, stations: list[str]) -> pd.DataFrame:
    X = p[["hour_sin", "hour_cos", "weekday", "is_weekend", "lag_7", "roll7"]].copy()
    for s in stations:
        X[f"st_{s}"] = (p["station_id"] == s).astype(int)
    return X


def _mk_model() -> HistGradientBoostingRegressor:
    # Poisson loss suits non-negative COUNT data (bookings per hour)
    return HistGradientBoostingRegressor(loss="poisson", max_iter=200, learning_rate=0.06,
                                        max_depth=6, min_samples_leaf=40, random_state=42)


def _errors(actual, pred) -> tuple[float, float]:
    err = np.asarray(actual, float) - np.asarray(pred, float)
    return float(np.abs(err).mean()), float(np.sqrt((err ** 2).mean()))


def forecast_demand(bookings: pd.DataFrame, test_days: int = 14,
                    horizon: int = HORIZON_DAYS) -> ForecastResult:
    """Train, evaluate against the baseline, and predict the next `horizon` days."""
    if bookings.empty:
        raise ForecastError("No bookings available for forecasting.")
    n_days = bookings["start_time"].dt.normalize().nunique()
    if n_days < MIN_HISTORY_DAYS:
        raise ForecastError(f"Need at least {MIN_HISTORY_DAYS} days of history "
                            f"(found {n_days}). Widen the date filter.")

    panel, last = _panel(bookings, horizon)
    feat = _features(panel)
    stations = sorted(feat["station_id"].unique())
    labeled = feat[(feat["date"] <= last) & feat["lag_7"].notna() & feat["roll7"].notna()]
    cutoff = last - pd.Timedelta(days=test_days - 1)
    train, test = labeled[labeled["date"] < cutoff], labeled[labeled["date"] >= cutoff]
    if len(train) < 500 or test.empty:
        raise ForecastError("Not enough history to hold out a test period. "
                            "Use a longer date range or fewer test days.")

    # baseline: historical mean per (station, weekday, hour)
    base = (train.groupby(["station_id", "weekday", "hour"])["count"].mean()
            .rename("baseline").reset_index())
    test = test.merge(base, on=["station_id", "weekday", "hour"], how="left")
    test["baseline"] = test["baseline"].fillna(train["count"].mean())

    model = _mk_model().fit(_matrix(train, stations), train["count"])
    test["model"] = np.clip(model.predict(_matrix(test, stations)), 0, None)

    mae_n, rmse_n = _errors(test["count"], test["lag_7"])
    mae_b, rmse_b = _errors(test["count"], test["baseline"])
    mae_m, rmse_m = _errors(test["count"], test["model"])
    metrics = pd.DataFrame({
        "method": ["Naive (same hour last week)", "Baseline (historical average)",
                "ML model (Poisson gradient boosting)"],
        "MAE": [round(mae_n, 3), round(mae_b, 3), round(mae_m, 3)],
        "RMSE": [round(rmse_n, 3), round(rmse_b, 3), round(rmse_m, 3)],
    })
    metrics["MAE_vs_baseline_pct"] = [round(100 * (mae_b - m) / mae_b, 1) if mae_b else 0.0
                                    for m in (mae_n, mae_b, mae_m)]

    Xte = _matrix(test, stations)
    pi = permutation_importance(model, Xte, test["count"], n_repeats=3, random_state=0,
                                scoring="neg_mean_absolute_error")
    imp = pd.DataFrame({"feature": Xte.columns, "importance": pi.importances_mean.round(4)})
    imp = imp.sort_values("importance", ascending=False).head(8).reset_index(drop=True)

    # final model on ALL labeled history -> forecast the future days
    final = _mk_model().fit(_matrix(labeled, stations), labeled["count"])
    fut = feat[feat["date"] > last].dropna(subset=["lag_7", "roll7"]).copy()
    fut["predicted_bookings"] = np.clip(final.predict(_matrix(fut, stations)), 0, None).round(2)
    fut["ts"] = fut["date"] + pd.to_timedelta(fut["hour"], unit="h")

    test["ts"] = test["date"] + pd.to_timedelta(test["hour"], unit="h")
    tp = test[["station_id", "ts", "count", "baseline", "model"]].rename(columns={"count": "actual"})
    return ForecastResult(metrics=metrics, test_predictions=tp.reset_index(drop=True),
                        future=fut[["station_id", "ts", "predicted_bookings"]].reset_index(drop=True),
                        importances=imp, test_days=test_days)
