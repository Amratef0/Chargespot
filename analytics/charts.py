"""Plotly figure builders (Member 4). Each function returns a go.Figure and
contains no Streamlit code, so the same charts can be used in notebooks/reports."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from analytics import metrics as M

PALETTE = ["#2E86AB", "#F6AE2D", "#33A17B", "#E4572E", "#8E6C8A"]
STATUS_COLORS = {"Completed": "#33A17B", "Cancelled": "#E4572E", "No-Show": "#F6AE2D",
                 "Confirmed": "#2E86AB", "Waiting": "#8E6C8A"}


def _tidy(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=50, b=10),
                      legend=dict(orientation="h", y=-0.2))
    return fig


def bookings_by_hour(bookings: pd.DataFrame) -> go.Figure:
    d = M.demand_by_hour(bookings)
    peak = d["bookings"].max() if len(d) else 0
    colors = [PALETTE[3] if v == peak and peak > 0 else PALETTE[0] for v in d["bookings"]]
    fig = go.Figure(go.Bar(x=d["hour"], y=d["bookings"], marker_color=colors))
    fig.update_layout(title="Bookings by start hour (peak in red)",
                      xaxis=dict(title="Hour of day", dtick=1), yaxis_title="Bookings")
    return _tidy(fig)


def demand_heatmap(bookings: pd.DataFrame) -> go.Figure:
    m = M.demand_heatmap(bookings)
    fig = px.imshow(m, aspect="auto", color_continuous_scale="YlOrRd",
                    labels=dict(x="Hour", y="Weekday", color="Bookings"))
    fig.update_layout(title="Demand heatmap: weekday x hour")
    return _tidy(fig, 340)


def daily_trend(bookings: pd.DataFrame) -> go.Figure:
    d = M.daily_demand(bookings)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d["date"], y=d["bookings"], name="Daily bookings",
                             mode="lines", line=dict(color="#B8D4E3", width=1)))
    fig.add_trace(go.Scatter(x=d["date"], y=d["rolling_avg"], name="7-day average",
                             mode="lines", line=dict(color=PALETTE[0], width=3)))
    fig.update_layout(title="Daily demand over time", yaxis_title="Bookings")
    return _tidy(fig)


def weekday_demand(bookings: pd.DataFrame) -> go.Figure:
    d = M.demand_by_weekday(bookings)
    colors = [PALETTE[1] if w in ("Fri", "Sat") else PALETTE[0] for w in d["weekday"]]
    fig = go.Figure(go.Bar(x=d["weekday"], y=d["avg_per_day"], marker_color=colors))
    fig.update_layout(title="Average bookings per day (weekend in yellow)", yaxis_title="Bookings / day")
    return _tidy(fig, 320)


def utilization_by_station(util: pd.DataFrame) -> go.Figure:
    d = util.sort_values("utilization_pct")
    fig = go.Figure(go.Bar(x=d["utilization_pct"], y=d["name"], orientation="h",
                           marker_color=PALETTE[0],
                           text=d["utilization_pct"].map("{:.1f}%".format), textposition="outside"))
    fig.update_layout(title="Utilization by station", xaxis_title="Utilization (%)")
    return _tidy(fig)


def status_distribution(bookings: pd.DataFrame) -> go.Figure:
    d = M.status_counts(bookings)
    fig = go.Figure(go.Pie(labels=d["status"], values=d["bookings"], hole=0.5,
                           marker_colors=[STATUS_COLORS.get(s, "#999") for s in d["status"]]))
    fig.update_layout(title="Booking status distribution")
    return _tidy(fig, 340)


def station_comparison(stats: pd.DataFrame, column: str, title: str, unit: str) -> go.Figure:
    d = stats.sort_values(column)
    fig = go.Figure(go.Bar(x=d[column], y=d["name"], orientation="h", marker_color=PALETTE[3]))
    fig.update_layout(title=title, xaxis_title=unit)
    return _tidy(fig, 340)


def search_comparison(df: pd.DataFrame) -> go.Figure:
    fig = px.line(df, x="size", y="avg_comparisons", color="algorithm", markers=True,
                  log_x=True, log_y=True, color_discrete_sequence=[PALETTE[3], PALETTE[0]])
    fig.update_layout(title="Average comparisons: sequential vs binary search (log scales)",
                      xaxis_title="Number of records", yaxis_title="Average comparisons")
    return _tidy(fig)


def forecast_vs_actual(tp: pd.DataFrame, station_id: str) -> go.Figure:
    d = tp[tp["station_id"] == station_id].copy()
    d["day"] = d["ts"].dt.normalize()
    d = d.groupby("day")[["actual", "baseline", "model"]].sum().reset_index()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d["day"], y=d["actual"], name="Actual", mode="lines+markers",
                             line=dict(color="#8A94A0", width=3)))   # mid-grey: readable on light AND dark
    fig.add_trace(go.Scatter(x=d["day"], y=d["baseline"], name="Baseline", mode="lines",
                             line=dict(color=PALETTE[1], dash="dot")))
    fig.add_trace(go.Scatter(x=d["day"], y=d["model"], name="ML model", mode="lines+markers",
                             line=dict(color=PALETTE[0])))
    fig.update_layout(title=f"Hold-out test: daily bookings, {station_id}", yaxis_title="Bookings / day")
    return _tidy(fig)


def forecast_next_days(fut: pd.DataFrame, station_id: str) -> go.Figure:
    d = fut[fut["station_id"] == station_id]
    fig = px.line(d, x="ts", y="predicted_bookings", color_discrete_sequence=[PALETTE[0]])
    fig.update_layout(title=f"Predicted bookings per hour, next 7 days ({station_id})",
                      yaxis_title="Bookings / hour", xaxis_title="")
    return _tidy(fig)


def defects_chart(report_df: pd.DataFrame) -> go.Figure:
    d = report_df.sort_values("rows")
    fig = px.bar(d, x="rows", y="defect", color="action", orientation="h",
                 color_discrete_map={"dropped": PALETTE[3], "fixed": PALETTE[2]})
    fig.update_layout(title="Data-quality defects found and handled", xaxis_title="Rows")
    return _tidy(fig, 380)


# ---------------------------------------------------------------- recommendation / scheduling / maintenance
_CRIT_COLORS = {"distance": "#2E86AB", "wait": "#E4572E", "price": "#F6AE2D",
                "power": "#33A17B", "availability": "#8E6C8A"}


def recommendation_breakdown(ranked: pd.DataFrame) -> go.Figure:
    """Stacked bars: how many score points each criterion contributes per station."""
    d = ranked.iloc[::-1]
    fig = go.Figure()
    for c, color in _CRIT_COLORS.items():
        fig.add_trace(go.Bar(y=d["name"], x=d[f"pts_{c}"], name=c.capitalize(), orientation="h",
                             marker_color=color))
    fig.update_layout(barmode="stack", title="Why each station scored what it did (points per criterion)",
                      xaxis_title="Score (0-100)")
    return _tidy(fig, 60 + 45 * len(d) + 120)


def scheduling_cost(summary: pd.DataFrame) -> go.Figure:
    d = summary.copy()
    colors = [PALETTE[3] if s == "fcfs" else (PALETTE[2] if s in ("optimal", "local_search") else PALETTE[0])
              for s in d["strategy"]]
    fig = go.Figure(go.Bar(x=d["strategy"], y=d["cost"], marker_color=colors,
                           text=d["cost"], textposition="outside"))
    fig.update_layout(title="Scheduling cost by strategy (total wait + penalty per unserved driver)",
                      yaxis_title="Cost (minutes)")
    return _tidy(fig, 340)


def schedule_timeline(plan_df: pd.DataFrame, title: str) -> go.Figure:
    d = plan_df.copy()
    fig = px.timeline(d, x_start="start_dt", x_end="end_dt", y="charger_id", color="wait",
                      color_continuous_scale="YlOrRd", hover_data=["req_id", "wait"],
                      labels={"wait": "Wait (min)"})
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(title=title)
    return _tidy(fig, 320)


def health_timeseries(health: pd.DataFrame, charger_id: str) -> go.Figure:
    from plotly.subplots import make_subplots
    d = health[health["charger_id"] == charger_id].sort_values("date")
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        subplot_titles=("Power ratio (delivered / rated)", "Errors per day", "Temperature (C)"))
    for i, (col, color) in enumerate((("power_ratio", PALETTE[0]), ("error_count", PALETTE[3]),
                                      ("temp_c", PALETTE[1])), start=1):
        fig.add_trace(go.Scatter(x=d["date"], y=d[col], mode="lines", line=dict(color="#C9D6DF", width=1),
                                 showlegend=False), row=i, col=1)
        fig.add_trace(go.Scatter(x=d["date"], y=d[col].rolling(7, min_periods=1).mean(), mode="lines",
                                 line=dict(color=color, width=3), showlegend=False), row=i, col=1)
    fig.update_layout(title=f"Health trend of {charger_id} (thick line = 7-day average)")
    return _tidy(fig, 520)


def risk_bar(assess: pd.DataFrame) -> go.Figure:
    d = assess.dropna(subset=["risk_score"]).sort_values("risk_score").tail(15)
    colors = [{"High": PALETTE[3], "Medium": PALETTE[1]}.get(l, PALETTE[2]) for l in d["risk_level"]]
    fig = go.Figure(go.Bar(x=d["risk_score"], y=d["charger_id"], orientation="h", marker_color=colors))
    fig.update_layout(title="Charger inspection risk (top 15)", xaxis_title="Risk score (0-100)")
    return _tidy(fig, 420)