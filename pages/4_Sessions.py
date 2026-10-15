"""Charging sessions (Member 3's module): start/complete with planned vs actual time, Merge-sorted history."""
from datetime import date, datetime, time

import pandas as pd
import streamlit as st

from core.state import get_app, require_page
from core.ui import flash, run_action, show_flash

user = require_page("sessions")
app = get_app()
st.title("Charging Sessions")
show_flash()
st.caption("Planned time comes from the booking; actual time is recorded when the session starts. "
           "Use the 'simulated time' boxes to demo without waiting.")

tab_go, tab_hist = st.tabs(["Start / complete", "History"])
with tab_go:
    day = st.date_input("Bookings for", date.today())
    lo, hi = datetime.combine(day, time(0)), datetime.combine(day, time(23, 59))
    ready = [b for b in app.bookings.list_bookings(status="Confirmed") if lo <= b.start_time <= hi]
    active_ids = {s.booking_id for s in app.sessions.sessions if s.status == "Active"}
    ready = [b for b in ready if b.booking_id not in active_ids]
    st.subheader("Ready to start")
    if not ready:
        st.info("No confirmed bookings waiting to start on this day.")
    else:
        sel = st.selectbox("Booking", ready, format_func=lambda b: f"#{b.booking_id} · {b.driver_id} · {b.station_name} · "
                                                                    f"{b.charger_id} · {b.start_time:%H:%M}")
        t = st.time_input("Simulated start time", sel.start_time.time())
        c = st.columns(2)
        if c[0].button("▶️ Start session"):
            ok, s = run_action(app.start_session, user, sel.booking_id, datetime.combine(sel.start_time.date(), t))
            if ok:
                flash(f"Session {s.session_id} started on {sel.charger_id} (now Occupied).")
                st.rerun()
        if c[1].button("🚫 Mark no-show"):
            ok, _ = run_action(app.mark_no_show, user, sel.booking_id)
            if ok:
                flash("Marked as no-show.", "warning")
                st.rerun()
    st.subheader("Active sessions")
    active = [s for s in app.sessions.sessions if s.status == "Active"]
    if not active:
        st.info("No active sessions.")
    else:
        s = st.selectbox("Session", active, format_func=lambda s: f"#{s.session_id} · booking {s.booking_id} · {s.charger_id} · started {s.start_time:%H:%M}")
        b = app.bookings.get_booking(s.booking_id)
        end_t = st.time_input("Simulated end time", (s.start_time + pd.Timedelta(minutes=b.duration_min)).time())
        end_dt = datetime.combine(s.start_time.date(), end_t)
        mins = max(1.0, (end_dt - s.start_time).total_seconds() / 60)
        energy = st.number_input("Energy delivered (kWh, simulated)", 0.0, 300.0, float(app.suggest_energy(b, mins)), 0.5)
        if st.button("⏹ Complete session"):
            ok, res = run_action(app.complete_session, user, s.session_id, energy, end_dt)
            if ok:
                sess, promoted = res
                st.success(f"Completed: {sess.duration_minutes} min, {sess.energy_delivered_kwh} kWh. Charger is Available again.")
                for req, nb in promoted:
                    st.info(f"Waiting driver {req['driver_id']} was promoted to booking #{nb.booking_id}.")

with tab_hist:
    c = st.columns(4)
    driver = c[0].text_input("Driver ID (e.g. D101)")
    charger = c[1].text_input("Charger ID (e.g. DC-213)")
    status = c[2].selectbox("Status", [None, "Planned", "Active", "Completed"])
    key = c[3].selectbox("Sort by", ["start_time", "duration", "energy"])
    rev = st.checkbox("Largest / newest first", True)
    rows = app.sessions.filter_sessions(driver or None, charger or None, status)
    rows = rows[-3000:]
    ordered, comps = app.sessions.sort_session_history(key, rev, rows)
    st.caption(f"{len(ordered):,} sessions shown (latest 3000 of the filter) · Merge Sort used {comps:,} comparisons.")
    st.dataframe(pd.DataFrame([{"Session": s.session_id, "Booking": s.booking_id, "Driver": s.user_id, "Charger": s.charger_id,
                                "Planned start": s.planned_start, "Actual start": s.start_time, "Actual end": s.end_time,
                                "Minutes": s.duration_minutes, "kWh": s.energy_delivered_kwh, "Status": s.status}
                               for s in ordered[:300]]), hide_index=True, width="stretch")
