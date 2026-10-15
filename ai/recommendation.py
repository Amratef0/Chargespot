"""Smart station recommendation (optional AI feature - Member 2's idea, built by Member 4).

Ranks stations for a driver and EXPLAINS the ranking. Rule-based, no training:

    score = 100 * sum(weight_i * s_i) / sum(weight_i)

where every criterion is scaled to 0..1 (1 = best) on an ABSOLUTE, explainable scale:
    distance     1 - min(km, 30) / 30          (30 km or more = 0)
    wait         1 - min(minutes, 60) / 60     (60 min or more = 0)
    power        min(kW, 150) / 150            (150 kW or more = 1)
    availability free compatible chargers / compatible chargers
    price        min-max across the eligible stations (no natural cap)
(Absolute scales matter: with min-max, one far-away station such as Alexandria
would squash the difference between a 3 km and a 10 km station.)

* eligible = open at the requested hour AND has an active (not in Maintenance)
  charger with the driver's connector. Others are returned in `excluded` with
  the reason, so nothing disappears silently.
* expected wait is DATA-DRIVEN: the historical average wait of bookings at that
  station (same connector) starting within +-1 hour of the requested hour,
  counting bookings that did not wait as 0.
* availability = compatible chargers currently "Available" / compatible chargers.

Distances come from the team's matrix (data/distances.json: driver's area -> station address).
Pure function: DataFrames in, result out (works with changed data, easy to test).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from core.schema import CONNECTORS

CRITERIA = ("distance", "wait", "price", "power", "availability")
LOWER_IS_BETTER = {"distance", "wait", "price"}
MIN_BOOKINGS_FOR_HOURLY_WAIT = 20
CAP_DISTANCE_KM = 30.0
CAP_WAIT_MIN = 60.0
CAP_POWER_KW = 150.0


@dataclass(frozen=True)
class Weights:
    distance: float = 0.30
    wait: float = 0.30
    price: float = 0.15
    power: float = 0.15
    availability: float = 0.10

    def validated(self) -> "Weights":
        vals = [getattr(self, c) for c in CRITERIA]
        if any(v < 0 for v in vals):
            raise ValueError("Weights cannot be negative.")
        if sum(vals) <= 0:
            raise ValueError("At least one weight must be greater than zero.")
        return self


@dataclass
class RecommendationResult:
    ranked: pd.DataFrame
    excluded: pd.DataFrame
    weights: Weights = field(default_factory=Weights)


def _scale(values: pd.Series, lower_is_better: bool) -> pd.Series:
    lo, hi = values.min(), values.max()
    if hi == lo:                                # all equal -> criterion does not discriminate
        return pd.Series(1.0, index=values.index)
    s = (values - lo) / (hi - lo)
    return 1 - s if lower_is_better else s


def _expected_wait(bookings: pd.DataFrame, station_id: str, connector: str, hour: int) -> tuple[float, str]:
    b = bookings[(bookings["station_id"] == station_id) & (bookings["connector"] == connector)]
    if b.empty:
        return 0.0, "no history"
    hrs = b["start_time"].dt.hour
    near = b[((hrs - hour).abs() <= 1) | ((hrs - hour).abs() >= 23)]       # wraps around midnight
    if len(near) >= MIN_BOOKINGS_FOR_HOURLY_WAIT:
        return float(near["wait_min"].mean()), f"based on {len(near):,} bookings near {hour:02d}:00"
    return float(b["wait_min"].mean()), f"all-day average ({len(b):,} bookings; few near {hour:02d}:00)"


def _explain(row: pd.Series, scaled: pd.Series) -> str:
    good = {
        "distance": f"close by ({row['distance_km']:.1f} km)",
        "wait": f"short expected wait ({row['expected_wait_min']:.0f} min)",
        "price": f"low price ({row['price_per_kwh']:.1f} EGP/kWh)",
        "power": f"fast charging (up to {row['max_power_kw']:.0f} kW)",
        "availability": f"{int(row['free_now'])}/{int(row['compatible_chargers'])} compatible chargers free now",
    }
    bad = {
        "distance": f"farther away ({row['distance_km']:.1f} km)",
        "wait": f"longer expected wait ({row['expected_wait_min']:.0f} min)",
        "price": f"higher price ({row['price_per_kwh']:.1f} EGP/kWh)",
        "power": f"slower chargers (max {row['max_power_kw']:.0f} kW)",
        "availability": f"few chargers free now ({int(row['free_now'])}/{int(row['compatible_chargers'])})",
    }
    strengths = [good[c] for c in CRITERIA if scaled[c] >= 0.8][:3]
    weaknesses = [bad[c] for c in CRITERIA if scaled[c] <= 0.25][:2]
    text = "Strengths: " + ", ".join(strengths) if strengths else "No standout strength"
    if weaknesses:
        text += ". Trade-offs: " + ", ".join(weaknesses)
    return text + "."


def recommend_stations(stations: pd.DataFrame, chargers: pd.DataFrame, bookings: pd.DataFrame,
                       driver_area: str, connector: str, target_hour: int, distances: dict,
                       weights: Weights | None = None, max_distance_km: float | None = None,
                       top_n: int | None = None) -> RecommendationResult:
    """Rank stations for one driver request. Raises ValueError on invalid input."""
    w = (weights or Weights()).validated()
    if connector not in CONNECTORS:
        raise ValueError(f"Unknown connector '{connector}'. Choose one of: {', '.join(CONNECTORS)}.")
    if driver_area not in distances:
        raise ValueError(f"Unknown area '{driver_area}'. Choose one of: {', '.join(distances)}.")
    if isinstance(target_hour, bool) or not isinstance(target_hour, int) or not 0 <= target_hour <= 23:
        raise ValueError("Target hour must be a whole number from 0 to 23.")

    rows, excluded = [], []
    for st in stations.itertuples(index=False):
        dist = distances[driver_area].get(st.address)            # Member 2's matrix: area -> station address
        ch = chargers[(chargers["station_id"] == st.station_id) & (chargers["status"] != "Maintenance")
                      & (chargers["connector"] == connector)]
        reason = None
        if dist is None:
            reason = f"no route data from {driver_area}"
        elif not (st.open_hour <= target_hour < st.close_hour):
            reason = f"closed at {target_hour:02d}:00 (open {st.open_hour:02d}:00-{st.close_hour:02d}:00)"
        elif ch.empty:
            reason = f"no active {connector} charger"
        elif max_distance_km is not None and dist > max_distance_km:
            reason = f"{dist:.1f} km away (limit {max_distance_km:g} km)"
        if reason:
            excluded.append({"station_id": st.station_id, "name": st.name, "distance_km": dist, "reason": reason})
            continue
        wait, basis = _expected_wait(bookings, st.station_id, connector, int(target_hour))
        rows.append({"station_id": st.station_id, "name": st.name, "city": st.city, "lat": st.lat,
                     "lon": st.lon, "distance_km": float(dist), "expected_wait_min": round(wait, 1),
                     "wait_basis": basis, "price_per_kwh": st.price_per_kwh,
                     "max_power_kw": float(ch["power_kw"].max()), "compatible_chargers": len(ch),
                     "free_now": int((ch["status"] == "Available").sum())})
    ex = pd.DataFrame(excluded, columns=["station_id", "name", "distance_km", "reason"])
    if not rows:
        return RecommendationResult(ranked=pd.DataFrame(), excluded=ex, weights=w)

    df = pd.DataFrame(rows)
    df["availability_ratio"] = df["free_now"] / df["compatible_chargers"]
    scaled = pd.DataFrame({
        "distance": 1 - df["distance_km"].clip(upper=CAP_DISTANCE_KM) / CAP_DISTANCE_KM,
        "wait": 1 - df["expected_wait_min"].clip(upper=CAP_WAIT_MIN) / CAP_WAIT_MIN,
        "price": _scale(df["price_per_kwh"], True),
        "power": df["max_power_kw"].clip(upper=CAP_POWER_KW) / CAP_POWER_KW,
        "availability": df["availability_ratio"]})
    total = sum(getattr(w, c) for c in CRITERIA)
    for c in CRITERIA:                                  # weighted points each criterion contributes
        df[f"pts_{c}"] = (100 * getattr(w, c) * scaled[c] / total).round(2)
    df["score"] = df[[f"pts_{c}" for c in CRITERIA]].sum(axis=1).round(1)
    df["why"] = [_explain(df.iloc[i], scaled.iloc[i]) for i in range(len(df))]
    df = df.sort_values(["score", "distance_km"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
    df.insert(0, "rank", range(1, len(df) + 1))
    if top_n:
        df = df.head(top_n)
    return RecommendationResult(ranked=df, excluded=ex, weights=w)
