from __future__ import annotations

import pandas as pd

from core.schema import WEEKDAY_NAMES, WEEKEND_DAYS

DECIDED = ("Completed", "Cancelled", "No-Show")


# ---------------------------------------------------------------- filtering
def filter_period(bookings: pd.DataFrame, sessions: pd.DataFrame,
                start=None, end=None, station_ids=None, connectors=None):
    """Apply the dashboard filters to bookings and sessions consistently."""
    b, s = bookings, sessions
    if start is not None:
        b = b[b["start_time"] >= pd.Timestamp(start)]
        s = s[s["actual_start"] >= pd.Timestamp(start)]
    if end is not None:
        limit = pd.Timestamp(end) + pd.Timedelta(days=1)       # inclusive end date
        b = b[b["start_time"] < limit]
        s = s[s["actual_start"] < limit]
    if station_ids is not None:
        b = b[b["station_id"].isin(station_ids)]
        s = s[s["station_id"].isin(station_ids)]
    if connectors is not None:
        b = b[b["connector"].isin(connectors)]
    if connectors is not None and "booking_id" in s.columns:
        s = s[s["booking_id"].isin(b["booking_id"])]
    return b, s


# ---------------------------------------------------------------- rates
def status_counts(bookings: pd.DataFrame) -> pd.DataFrame:
    vc = bookings["status"].value_counts()
    out = vc.rename_axis("status").reset_index(name="bookings")
    out["share_pct"] = (100 * out["bookings"] / max(len(bookings), 1)).round(1)
    return out


def rate(bookings: pd.DataFrame, status: str) -> float:
    """Share (0-100) of decided bookings having `status`."""
    decided = bookings[bookings["status"].isin(DECIDED)]
    if decided.empty:
        return 0.0
    return float(round(100.0 * (decided["status"] == status).mean(), 1))


def completion_rate(b): return rate(b, "Completed")
def cancellation_rate(b): return rate(b, "Cancelled")
def no_show_rate(b): return rate(b, "No-Show")


def waiting_stats(bookings: pd.DataFrame) -> dict:
    q = bookings[bookings["queued"] == 1]
    return {
        "queued_bookings": int(len(q)),
        "queued_share_pct": round(100.0 * len(q) / len(bookings), 1) if len(bookings) else 0.0,
        "avg_wait_min": round(float(q["wait_min"].mean()), 1) if len(q) else 0.0,
        "max_wait_min": int(q["wait_min"].max()) if len(q) else 0,
    }


def delay_stats(sessions: pd.DataFrame) -> dict:
    if sessions.empty:
        return {"avg_delay_min": 0.0, "delayed_over_10_pct": 0.0}
    return {
        "avg_delay_min": round(float(sessions["delay_min"].mean()), 1),
        "delayed_over_10_pct": float(round(100.0 * (sessions["delay_min"] > 10).mean(), 1)),
    }


# ---------------------------------------------------------------- time based
def demand_by_hour(bookings: pd.DataFrame) -> pd.DataFrame:
    h = bookings["start_time"].dt.hour.value_counts().reindex(range(24), fill_value=0)
    return h.rename_axis("hour").reset_index(name="bookings")


def demand_by_weekday(bookings: pd.DataFrame) -> pd.DataFrame:
    """Total and average-per-day bookings for each weekday."""
    if bookings.empty:
        return pd.DataFrame({"weekday": WEEKDAY_NAMES, "bookings": 0, "avg_per_day": 0.0})
    dates = bookings["start_time"].dt.normalize()
    daily = dates.value_counts().rename_axis("date").reset_index(name="n")
    daily["wd"] = daily["date"].dt.weekday
    g = daily.groupby("wd")["n"].agg(["sum", "mean"]).reindex(range(7), fill_value=0)
    return pd.DataFrame({"weekday": WEEKDAY_NAMES, "bookings": g["sum"].astype(int).to_numpy(),
                        "avg_per_day": g["mean"].round(1).to_numpy()})


def demand_heatmap(bookings: pd.DataFrame) -> pd.DataFrame:
    """Matrix weekday (rows) x hour (columns) of booking counts."""
    m = pd.crosstab(bookings["start_time"].dt.weekday, bookings["start_time"].dt.hour)
    m = m.reindex(index=range(7), columns=range(24), fill_value=0)
    m.index = list(WEEKDAY_NAMES)
    return m


def daily_demand(bookings: pd.DataFrame, window: int = 7) -> pd.DataFrame:
    """Bookings per calendar day (gaps filled with 0) + rolling mean."""
    if bookings.empty:
        return pd.DataFrame(columns=["date", "bookings", "rolling_avg"])
    d = bookings["start_time"].dt.normalize().value_counts().sort_index()
    d = d.reindex(pd.date_range(d.index.min(), d.index.max(), freq="D"), fill_value=0)
    out = d.rename_axis("date").reset_index(name="bookings")
    out["rolling_avg"] = out["bookings"].rolling(window, min_periods=1).mean().round(2)
    return out


def weekly_demand(bookings: pd.DataFrame) -> pd.DataFrame:
    if bookings.empty:
        return pd.DataFrame(columns=["week", "bookings"])
    w = bookings.set_index("start_time").resample("W-SUN")["booking_id"].count()
    return w.rename_axis("week").reset_index(name="bookings")


def peak_hours(bookings: pd.DataFrame, top: int = 3) -> pd.DataFrame:
    h = demand_by_hour(bookings)
    h = h.sort_values(["bookings", "hour"], ascending=[False, True], kind="mergesort")
    return h.head(top).reset_index(drop=True)


def peak_hour(bookings: pd.DataFrame):
    """Hour (0-23) with the most bookings, or None if there is no data."""
    if bookings.empty:
        return None
    return int(peak_hours(bookings, 1).loc[0, "hour"])


# ---------------------------------------------------------------- stations
def station_utilization(sessions: pd.DataFrame, chargers: pd.DataFrame,
                        stations: pd.DataFrame, start=None, end=None) -> pd.DataFrame:
    """One row per station with utilization %, energy, revenue, session count."""
    if start is None or end is None:
        if sessions.empty:
            days = 1
        else:
            start = sessions["actual_start"].min().normalize()
            end = sessions["actual_start"].max().normalize()
            days = (end - start).days + 1
    else:
        days = (pd.Timestamp(end).normalize() - pd.Timestamp(start).normalize()).days + 1
    days = max(days, 1)

    active = chargers[chargers["status"] != "Maintenance"]
    n_ch = active.groupby("station_id").size()
    agg = sessions.groupby("station_id").agg(
        busy_min=("duration_min", "sum"), sessions=("session_id", "count"),
        energy_kwh=("energy_kwh", "sum"), revenue_egp=("cost_egp", "sum"),
        avg_delay_min=("delay_min", "mean"))

    out = stations[["station_id", "name", "city"]].copy().set_index("station_id")
    out["open_hours"] = (stations.set_index("station_id")["close_hour"]
                        - stations.set_index("station_id")["open_hour"])
    out["active_chargers"] = n_ch.reindex(out.index).fillna(0).astype(int)
    out = out.join(agg).fillna({"busy_min": 0, "sessions": 0, "energy_kwh": 0,
                                "revenue_egp": 0, "avg_delay_min": 0})
    out["capacity_min"] = out["active_chargers"] * out["open_hours"] * 60 * days
    out["utilization_pct"] = (100 * out["busy_min"] / out["capacity_min"].where(out["capacity_min"] > 0)
                            ).clip(upper=100).fillna(0).round(1)
    for c in ("energy_kwh", "revenue_egp", "avg_delay_min"):
        out[c] = out[c].round(1)
    out["sessions"] = out["sessions"].astype(int)
    return out.reset_index()


def network_utilization(util: pd.DataFrame) -> float:
    cap = util["capacity_min"].sum()
    return float(round(100 * util["busy_min"].sum() / cap, 1)) if cap else 0.0


def station_booking_stats(bookings: pd.DataFrame, stations: pd.DataFrame) -> pd.DataFrame:
    """Bookings, cancellation rate and waiting time per station."""
    rows = []
    for sid, g in bookings.groupby("station_id"):
        w = waiting_stats(g)
        rows.append({"station_id": sid, "bookings": len(g),
                    "cancellation_rate_pct": cancellation_rate(g),
                    "no_show_rate_pct": no_show_rate(g),
                    "queued_share_pct": w["queued_share_pct"],
                    "avg_wait_min": w["avg_wait_min"]})
    out = pd.DataFrame(rows, columns=["station_id", "bookings", "cancellation_rate_pct",
                                    "no_show_rate_pct", "queued_share_pct", "avg_wait_min"])
    return stations[["station_id", "name"]].merge(out, on="station_id", how="left").fillna(0)


def connector_mix(bookings: pd.DataFrame) -> pd.DataFrame:
    return (bookings["connector"].value_counts().rename_axis("connector")
            .reset_index(name="bookings"))


# ---------------------------------------------------------------- KPI bundle
def kpi_summary(bookings: pd.DataFrame, sessions: pd.DataFrame,
                chargers: pd.DataFrame, stations: pd.DataFrame,
                start=None, end=None) -> dict:
    util = station_utilization(sessions, chargers, stations, start, end)
    ph = peak_hour(bookings)
    return {
        "total_bookings": int(len(bookings)),
        "completion_rate_pct": completion_rate(bookings),
        "cancellation_rate_pct": cancellation_rate(bookings),
        "no_show_rate_pct": no_show_rate(bookings),
        **waiting_stats(bookings),
        **delay_stats(sessions),
        "network_utilization_pct": network_utilization(util),
        "peak_hour": ph,
        "energy_kwh": round(float(sessions["energy_kwh"].sum()), 1),
        "revenue_egp": round(float(sessions["cost_egp"].sum()), 1),
    }


def is_weekend(ts_series: pd.Series) -> pd.Series:
    return ts_series.dt.weekday.isin(WEEKEND_DAYS)
