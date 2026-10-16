"""Predictive charger maintenance (optional AI feature, Member 4).

Flags chargers that should be INSPECTED, from their daily health readings
(power ratio, error count, temperature).

Method (rule-based trend scoring - fully explainable, no training needed):
    compare each charger's RECENT window with its OWN earlier REFERENCE window
        power drop      = reference mean power_ratio - recent mean   (percentage points)
        error increase  = recent mean errors/day     - reference mean
        temperature rise= recent mean temp           - reference mean
    each component is scaled to 0..1 by a "full-scale" value, then
        risk = 100 * (0.40*power + 0.35*errors + 0.25*temperature)
    levels: High >= 60, Medium >= 20, otherwise Low.
    (Medium threshold chosen by sweeping 15/20/25/30 over 60 simulated fleets: 20 caught
    100% of degrading chargers with ~2% false alarms; 30 missed ~13%. A missed failure
    costs more than one extra inspection.)

Why compare a charger with ITSELF? A charger that has always had many errors
(stable but noisy) is not deteriorating; a charger whose output is falling is.

IMPORTANT: the readings are SIMULATED, so results are only illustrative. The
evaluation against the simulation's ground truth shows the method works on
data that matches its assumptions - it does not prove real-world accuracy.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


class MaintenanceError(ValueError):
    """Raised with a friendly message when the data cannot be assessed."""


@dataclass(frozen=True)
class MaintenanceConfig:
    window_days: int = 14                 # "recent" period
    reference_days: int = 30              # the period before it
    full_power_drop_pp: float = 10.0      # 10 percentage points of lost power = max score
    full_error_increase: float = 1.0      # +1 error/day = max score
    full_temp_rise_c: float = 10.0        # +10 C = max score
    w_power: float = 0.40
    w_errors: float = 0.35
    w_temp: float = 0.25
    high_threshold: float = 60.0
    medium_threshold: float = 20.0       # chosen from a threshold sweep: see docs (cost of a miss > cost of a check)


REQUIRED = ("charger_id", "date", "power_ratio", "error_count", "temp_c")


def _level(score: float, cfg: MaintenanceConfig) -> str:
    if score >= cfg.high_threshold:
        return "High"
    if score >= cfg.medium_threshold:
        return "Medium"
    return "Low"


def assess_chargers(health: pd.DataFrame, chargers: pd.DataFrame | None = None,
                    stations: pd.DataFrame | None = None,
                    config: MaintenanceConfig | None = None) -> pd.DataFrame:
    """One row per charger with component deltas, risk score, level and reasons."""
    cfg = config or MaintenanceConfig()
    missing = [c for c in REQUIRED if c not in health.columns]
    if missing:
        raise MaintenanceError(f"Health data is missing column(s): {', '.join(missing)}")
    if health.empty:
        raise MaintenanceError("No health readings available.")
    need = cfg.window_days + cfg.reference_days

    last = health["date"].max()
    recent_start = last - pd.Timedelta(days=cfg.window_days - 1)
    ref_start = recent_start - pd.Timedelta(days=cfg.reference_days)

    rows = []
    for cid, g in health.groupby("charger_id"):
        recent = g[g["date"] >= recent_start]
        ref = g[(g["date"] >= ref_start) & (g["date"] < recent_start)]
        row = {"charger_id": cid, "readings": len(g)}
        enough = (recent["power_ratio"].notna().sum() >= cfg.window_days // 2
                  and ref["power_ratio"].notna().sum() >= cfg.reference_days // 2 and len(g) >= need // 2)
        if not enough:
            rows.append({**row, "power_drop_pp": np.nan, "error_increase_per_day": np.nan,
                        "temp_rise_c": np.nan, "risk_score": np.nan, "risk_level": "Insufficient data",
                        "reasons": "Not enough history to compare recent and reference periods."})
            continue
        drop = 100 * (ref["power_ratio"].mean() - recent["power_ratio"].mean())
        err = recent["error_count"].mean() - ref["error_count"].mean()
        temp = recent["temp_c"].mean() - ref["temp_c"].mean()
        comp = {
            "power": float(np.clip(drop / cfg.full_power_drop_pp, 0, 1)),
            "errors": float(np.clip(err / cfg.full_error_increase, 0, 1)),
            "temp": float(np.clip(temp / cfg.full_temp_rise_c, 0, 1)),
        }
        score = 100 * (cfg.w_power * comp["power"] + cfg.w_errors * comp["errors"] + cfg.w_temp * comp["temp"])
        reasons = []
        if comp["power"] >= 0.4:
            reasons.append(f"power output down {drop:.1f} pp vs the previous {cfg.reference_days} days")
        if comp["errors"] >= 0.4:
            reasons.append(f"errors up by {err:.2f}/day (now {recent['error_count'].mean():.2f}/day)")
        if comp["temp"] >= 0.4:
            reasons.append(f"temperature up {temp:.1f} C (now {recent['temp_c'].mean():.1f} C)")
        rows.append({**row, "power_drop_pp": round(drop, 2), "error_increase_per_day": round(err, 2),
                    "temp_rise_c": round(temp, 1), "risk_score": round(score, 1),
                    "risk_level": _level(score, cfg),
                    "reasons": "; ".join(reasons) if reasons else "no significant deterioration"})
    out = pd.DataFrame(rows)

    if chargers is not None:
        cols = [c for c in ("charger_id", "station_id", "charger_type", "connector", "power_kw", "status")
                if c in chargers.columns]
        out = out.merge(chargers[cols], on="charger_id", how="left")
        if stations is not None and "station_id" in out.columns:
            out = out.merge(stations[["station_id", "name"]].rename(columns={"name": "station"}),
                            on="station_id", how="left")
    order = {"High": 0, "Medium": 1, "Low": 2, "Insufficient data": 3}
    out = out.assign(_o=out["risk_level"].map(order)).sort_values(
        ["_o", "risk_score"], ascending=[True, False], kind="mergesort").drop(columns="_o")
    return out.reset_index(drop=True)


def inspection_list(assessment: pd.DataFrame) -> pd.DataFrame:
    """Chargers to inspect (High + Medium) - ready to export or hand to the station service."""
    return assessment[assessment["risk_level"].isin(["High", "Medium"])].reset_index(drop=True)


def evaluate_against_truth(assessment: pd.DataFrame, truth: pd.DataFrame) -> dict:
    """Precision/recall of flagging (High or Medium) vs the simulated ground truth."""
    m = assessment.merge(truth, on="charger_id", how="inner")
    m = m[m["risk_level"] != "Insufficient data"]
    flagged = m["risk_level"].isin(["High", "Medium"])
    tp = int((flagged & m["at_risk"]).sum())
    fp = int((flagged & ~m["at_risk"]).sum())
    fn = int((~flagged & m["at_risk"]).sum())
    tn = int((~flagged & ~m["at_risk"]).sum())
    return {
        "true_positives": tp, "false_positives": fp, "false_negatives": fn, "true_negatives": tn,
        "precision": round(tp / (tp + fp), 3) if tp + fp else None,
        "recall": round(tp / (tp + fn), 3) if tp + fn else None,
        "confusion": pd.DataFrame({"flagged": [tp, fp], "not flagged": [fn, tn]},
                                index=["really at risk", "really healthy"]),
        "by_class": m.groupby("true_class")["risk_level"].value_counts().unstack(fill_value=0),
    }
