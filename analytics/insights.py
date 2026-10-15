"""Written insights, GENERATED from the data (never hard-coded).

Every sentence is an f-string built from computed numbers, so the text
changes when the dataset changes ("No hard-coded final results").
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from analytics import metrics as M


@dataclass
class Insight:
    title: str
    text: str
    level: str = "info"        # info | warning | success


def _hh(h: int) -> str:
    return f"{h:02d}:00-{(h + 1) % 24:02d}:00"


def generate_insights(bookings, sessions, stations, chargers, start=None, end=None) -> list[Insight]:
    out: list[Insight] = []
    if bookings.empty:
        return [Insight("No data", "No bookings match the current filters.", "warning")]

    # 1. peak demand --------------------------------------------------------
    ph = M.peak_hours(bookings, 3)
    share = 100 * ph.loc[0, "bookings"] / len(bookings)
    others = ", ".join(_hh(int(h)) for h in ph.loc[1:, "hour"])
    out.append(Insight(
        "Peak demand hour",
        f"Demand peaks at {_hh(int(ph.loc[0, 'hour']))} with {int(ph.loc[0, 'bookings']):,} bookings "
        f"({share:.1f}% of all bookings). Next busiest: {others}. Operators should schedule "
        f"staff and keep chargers free in these windows.", "info"))

    # 2. busiest vs least-used station ------------------------------------
    util = M.station_utilization(sessions, chargers, stations, start, end)
    util = util[util["capacity_min"] > 0].sort_values("utilization_pct", ascending=False)
    if len(util) >= 2:
        top, low = util.iloc[0], util.iloc[-1]
        gap = top["utilization_pct"] - low["utilization_pct"]
        out.append(Insight(
            "Busiest vs least-used station",
            f"{top['name']} is the busiest station at {top['utilization_pct']:.1f}% utilization, while "
            f"{low['name']} is the least used at {low['utilization_pct']:.1f}% - a gap of {gap:.1f} points. "
            f"Directing overflow drivers from {top['name']} to {low['name']} (or adding chargers at "
            f"{top['name']}) would balance the network.", "warning" if gap > 15 else "info"))

    # 3. weekend vs weekday -------------------------------------------------
    daily = M.daily_demand(bookings)
    if len(daily) >= 14:
        wk = daily["date"].dt.weekday.isin([4, 5])
        wk_avg, wd_avg = daily.loc[wk, "bookings"].mean(), daily.loc[~wk, "bookings"].mean()
        if wd_avg > 0:
            diff = 100 * (wk_avg - wd_avg) / wd_avg
            direction = "higher" if diff >= 0 else "lower"
            out.append(Insight(
                "Weekend effect (Fri-Sat)",
                f"Fridays and Saturdays average {wk_avg:.0f} bookings/day versus {wd_avg:.0f} on other days "
                f"({abs(diff):.0f}% {direction}).", "info"))

    # 4. trend ---------------------------------------------------------------
    if len(daily) >= 56:
        first, last = daily["bookings"].iloc[:28].mean(), daily["bookings"].iloc[-28:].mean()
        if first > 0:
            g = 100 * (last - first) / first
            out.append(Insight(
                "Demand trend",
                f"Average daily demand in the last 4 weeks is {last:.0f} bookings versus {first:.0f} in the "
                f"first 4 weeks ({g:+.0f}%).", "success" if g > 0 else "warning"))

    # 5. cancellations --------------------------------------------------------
    sb = M.station_booking_stats(bookings, stations)
    sb = sb[sb["bookings"] >= 30]
    net_cancel = M.cancellation_rate(bookings)
    if not sb.empty:
        worst = sb.sort_values("cancellation_rate_pct", ascending=False).iloc[0]
        out.append(Insight(
            "Cancellation hotspot",
            f"{worst['name']} has the highest cancellation rate ({worst['cancellation_rate_pct']:.1f}% vs "
            f"{net_cancel:.1f}% network average).",
            "warning" if worst["cancellation_rate_pct"] > net_cancel + 5 else "info"))

    # 6. waiting list ---------------------------------------------------------
    w = M.waiting_stats(bookings)
    if w["queued_bookings"]:
        longest = sb.sort_values("avg_wait_min", ascending=False).iloc[0] if not sb.empty else None
        extra = f" Longest average wait: {longest['name']} ({longest['avg_wait_min']:.0f} min)." if longest is not None else ""
        out.append(Insight(
            "Waiting list pressure",
            f"{w['queued_share_pct']:.1f}% of bookings ({w['queued_bookings']:,}) had to join the waiting list, "
            f"with an average wait of {w['avg_wait_min']:.0f} minutes.{extra}", "warning" if w["queued_share_pct"] > 15 else "info"))

    # 7. punctuality ------------------------------------------------------
    d = M.delay_stats(sessions)
    if not sessions.empty:
        out.append(Insight(
            "Punctuality",
            f"Drivers start on average {d['avg_delay_min']:.1f} min after their planned time and "
            f"{d['delayed_over_10_pct']:.1f}% of sessions start more than 10 minutes late, which blocks "
            f"the next booking on the same charger.", "info"))

    # 8. revenue --------------------------------------------------------------
    if not util.empty and util["revenue_egp"].sum() > 0:
        r = util.sort_values("revenue_egp", ascending=False).iloc[0]
        out.append(Insight(
            "Revenue leader (simulated)",
            f"{r['name']} generated {r['revenue_egp']:,.0f} EGP "
            f"({100 * r['revenue_egp'] / util['revenue_egp'].sum():.0f}% of network revenue).", "success"))
    return out
