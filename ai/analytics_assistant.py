"""Rule-based analytics assistant (optional AI feature, Member 4).

Answers questions in English or Arabic using ONLY numbers computed by
analytics/metrics.py - it can never invent a figure. No API key, no internet,
so it also works as the offline fallback during the demo.

Optional upgrade (not needed for grading): pass the returned text to an LLM
only to REPHRASE it, never to compute numbers.
"""
from __future__ import annotations

import pandas as pd

from analytics import metrics as M

INTENTS = {
    "peak": ["peak", "busiest hour", "rush", "ذروة", "زحمة", "ساعة"],
    "busiest_station": ["busiest", "most used", "highest utilization", "اكتر محطة", "أكثر محطة", "الأكثر استخدام", "اكتر محطه"],
    "least_station": ["least", "lowest utilization", "idle", "اقل محطة", "أقل محطة", "الأقل استخدام"],
    "cancel": ["cancel", "no-show", "no show", "الغاء", "إلغاء", "كانسل"],
    "wait": ["wait", "queue", "waiting", "انتظار", "طابور"],
    "revenue": ["revenue", "income", "money", "earn", "ايراد", "إيراد", "دخل", "فلوس"],
    "energy": ["energy", "kwh", "طاقة", "كيلو"],
    "weekend": ["weekend", "friday", "saturday", "الجمعة", "السبت", "اجازة", "إجازة"],
    "delay": ["delay", "late", "punctual", "تأخير", "متأخر"],
    "summary": ["summary", "overview", "report", "kpi", "ملخص", "تقرير", "نظرة"],
}

SUGGESTIONS = [
    "When is the peak hour?",
    "Which station is the busiest?",
    "Which station has the most cancellations?",
    "How long do drivers wait?",
    "Give me a summary",
    "ايه ساعة الذروة؟",
]


class AnalyticsAssistant:
    def __init__(self, bookings, sessions, stations, chargers):
        self.b, self.s, self.st, self.ch = bookings, sessions, stations, chargers

    # -------------------------------------------------------------- routing
    def detect_intent(self, question: str) -> str | None:
        q = question.lower()
        scores = {k: sum(w in q for w in words) for k, words in INTENTS.items()}
        best = max(scores, key=scores.get)
        if scores[best] == 0:
            return None
        if best == "peak" and ("station" in q or "محطة" in q or "محطه" in q) and scores["busiest_station"]:
            return "busiest_station"
        return best

    def ask(self, question: str) -> str:
        if self.b.empty:
            return "There is no data for the current filters, so I cannot answer yet."
        intent = self.detect_intent(question)
        handler = getattr(self, f"_a_{intent}", None) if intent else None
        if handler is None:
            return ("I can answer questions about: peak hours, busiest/least-used stations, "
                    "cancellations, waiting time, revenue, energy, weekends, delays, or give a summary. "
                    "Try one of the suggested questions.")
        return handler()

    # -------------------------------------------------------------- answers
    def _util(self):
        u = M.station_utilization(self.s, self.ch, self.st)
        return u[u["capacity_min"] > 0]

    def _a_peak(self):
        ph = M.peak_hours(self.b, 3)
        f = lambda h: f"{int(h):02d}:00-{(int(h) + 1) % 24:02d}:00"
        return (f"Peak demand is {f(ph.loc[0, 'hour'])} with {int(ph.loc[0, 'bookings']):,} bookings. "
                f"Next: {', '.join(f(h) for h in ph.loc[1:, 'hour'])}.")

    def _a_busiest_station(self):
        u = self._util().sort_values("utilization_pct", ascending=False).iloc[0]
        return (f"{u['name']} is the busiest: {u['utilization_pct']:.1f}% utilization, "
                f"{int(u['sessions']):,} sessions, {u['energy_kwh']:,.0f} kWh delivered.")

    def _a_least_station(self):
        u = self._util().sort_values("utilization_pct").iloc[0]
        return f"{u['name']} is the least used: {u['utilization_pct']:.1f}% utilization over {int(u['sessions']):,} sessions."

    def _a_cancel(self):
        sb = M.station_booking_stats(self.b, self.st)
        sb = sb[sb["bookings"] > 0].sort_values("cancellation_rate_pct", ascending=False).iloc[0]
        return (f"Network cancellation rate is {M.cancellation_rate(self.b):.1f}% and no-show rate "
                f"{M.no_show_rate(self.b):.1f}%. Highest cancellations: {sb['name']} ({sb['cancellation_rate_pct']:.1f}%).")

    def _a_wait(self):
        w = M.waiting_stats(self.b)
        return (f"{w['queued_share_pct']:.1f}% of bookings joined the waiting list; the average wait is "
                f"{w['avg_wait_min']:.0f} min (max {w['max_wait_min']} min).")

    def _a_revenue(self):
        u = self._util().sort_values("revenue_egp", ascending=False)
        return (f"Total simulated revenue is {u['revenue_egp'].sum():,.0f} EGP. "
                f"Top station: {u.iloc[0]['name']} ({u.iloc[0]['revenue_egp']:,.0f} EGP).")

    def _a_energy(self):
        return f"{self.s['energy_kwh'].sum():,.0f} kWh were delivered across {len(self.s):,} sessions (simulated)."

    def _a_weekend(self):
        d = M.daily_demand(self.b)
        wk = d["date"].dt.weekday.isin([4, 5])
        if wk.all() or (~wk).all():
            return "The selected period does not include both weekend and weekday days."
        a, c = d.loc[wk, "bookings"].mean(), d.loc[~wk, "bookings"].mean()
        return f"Fri-Sat average {a:.0f} bookings/day vs {c:.0f} on other days ({100 * (a - c) / c:+.0f}%)."

    def _a_delay(self):
        d = M.delay_stats(self.s)
        return (f"Sessions start {d['avg_delay_min']:.1f} min late on average; "
                f"{d['delayed_over_10_pct']:.1f}% start more than 10 minutes late.")

    def _a_summary(self):
        k = M.kpi_summary(self.b, self.s, self.ch, self.st)
        return (f"{k['total_bookings']:,} bookings | completion {k['completion_rate_pct']}% | cancellation "
                f"{k['cancellation_rate_pct']}% | utilization {k['network_utilization_pct']}% | avg wait "
                f"{k['avg_wait_min']} min | peak hour {k['peak_hour']}:00 | revenue {k['revenue_egp']:,.0f} EGP.")
