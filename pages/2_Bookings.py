"""Bookings (Member 2's module). Driver: find a station (nearest available = greedy), book, see alternatives,
join the waiting list, cancel. Operator/admin: all bookings, Merge-sorted, and the charger x hour grid."""
from datetime import date, datetime, time, timedelta

import pandas as pd
import streamlit as st

from algorithms.interval_utils import minutes_to_time
from core.state import get_app, require_page
from core.ui import flash, run_action, show_flash
from services.scheduler import Scheduler

user = require_page("bookings")
app = get_app()
st.title("Bookings")
show_flash()
DURATIONS = [30, 45, 60, 90, 120, 180, 240]

def book_tab():
    veh = app.vehicle_of_driver(user.driver_id)
    if veh is None:
        st.warning("No vehicle is registered for your account.")
        st.stop()
    connector = veh["connector"]
    st.caption(f"Your vehicle: **{veh['vehicle_model']}** → connector **{connector}**. "
               "Only chargers with this connector are offered.")
    with st.form("search"):
        c = st.columns(4)
        area = c[0].selectbox("Your area", Scheduler.get_areas(app.stations.stations))
        day = c[1].date_input("Date", date.today(), min_value=date.today())
        slots = [minutes_to_time(m) for m in range(0, 24 * 60, 15)]
        hhmm = c[2].selectbox("Start time", slots, index=slots.index("10:00"))
        dur = c[3].selectbox("Duration (min)", DURATIONS, index=2)
        if st.form_submit_button("Find stations"):
            h, m = map(int, hhmm.split(":"))
            st.session_state["booking_search"] = {"area": area, "connector": connector, "duration": dur,
                                                  "start": datetime.combine(day, time(h, m))}
    q = st.session_state.get("booking_search")
    if q:
        options = app.find_station_options(q["area"], q["connector"], q["start"], q["duration"])
        if not options:
            st.warning("No station with a compatible charger has route data from your area.")
        else:
            best = Scheduler.find_best_station(options)
            st.write(f"**{q['start']:%a %d %b %H:%M} · {q['duration']} min** - stations ordered by availability, then distance:")
            st.dataframe(pd.DataFrame([{
                "#": i + 1, "Station": o["station"].name, "Distance (km)": o["distance"],
                "Status": "Available" if o["is_available"] else "Booked - waiting list / alternatives",
                "Charger (greedy)": o["charger_id"] or "-", "Recommended": "⭐" if o is best else ""}
                for i, o in enumerate(options)]), hide_index=True, width="stretch")
            pick = st.selectbox("Choose a station", options, index=options.index(best) if best else 0,
                                format_func=lambda o: f"{o['station'].name} ({o['distance']} km)")
            if pick["is_available"]:
                if st.button("✅ Confirm booking"):
                    ok, res = run_action(app.book_at_station, user, pick["station"], q["connector"], q["start"], q["duration"])
                    if ok and res["status"] == "confirmed":
                        b = res["booking"]
                        st.success(f"Booking #{b.booking_id} confirmed: {b.station_name}, charger {b.charger_id}, "
                                   f"{b.start_time:%d %b %H:%M}-{b.end_time:%H:%M}.")
                        st.session_state.pop("booking_search")
                    elif ok:
                        st.warning("Someone just took that slot. Search again.")
            else:
                st.warning("This slot is already booked at that station.")
                for i, alt in enumerate(pick["alternatives"]):
                    label = f"Book {minutes_to_time(alt.start_min)} on {alt.charger_id} (+{alt.wait_min} min)"
                    if st.button(label, key=f"alt{i}"):
                        ok, b = run_action(app.book_alternative, user, pick["station"], alt,
                                           q["start"].strftime("%Y-%m-%d"), q["duration"],
                                           success=lambda b: f"Booking #{b.booking_id} confirmed at {b.start_time:%H:%M}.")
                if st.button("⏳ Join the waiting list for the original time"):
                    ok, r = run_action(app.join_waiting_list, user, pick["station"], q["connector"], q["start"],
                                       q["duration"], success=lambda r: f"You are number {r['position']} in the waiting list "
                                                                       f"(request #{r['request_id']}).")



def mine_tab():
    mine = app.bookings.list_bookings(driver_id=user.driver_id) if user.driver_id else []
    if not mine:
        st.info("You have no bookings yet." if user.driver_id else "Operators and administrators have no personal bookings.")
    else:
        ordered, comps = app.bookings.sorted_by_start(mine, reverse=True)
        st.caption(f"Newest first, ordered with our Merge Sort ({comps} comparisons).")
        st.dataframe(pd.DataFrame([{"ID": b.booking_id, "Station": b.station_name, "Charger": b.charger_id,
                                    "Start": b.start_time, "End": b.end_time, "Status": b.status} for b in ordered[:200]]),
                     hide_index=True, width="stretch")
        active = [b for b in ordered if b.status == "Confirmed" and b.end_time > app.now()]
        if active:
            sel = st.selectbox("Cancel a booking", active, format_func=lambda b: f"#{b.booking_id} {b.station_name} {b.start_time:%d %b %H:%M}")
            if st.button("Cancel this booking"):
                ok, res = run_action(app.cancel_booking, user, sel.booking_id)
                if ok:
                    flash("Booking cancelled and the slot released.")
                    for req, nb in res[1]:
                        flash(f"The freed slot was given to waiting driver {req['driver_id']} (booking #{nb.booking_id}).", "info")
                    st.rerun()



def all_tab():
    c = st.columns(3)
    sid = c[0].selectbox("Station", app.stations.stations, format_func=lambda s: f"{s.station_id} - {s.name}", key="all_station")
    gday = c[1].date_input("Day", date.today(), key="all_day")
    status = c[2].selectbox("Status", [None, "Confirmed", "Completed", "Cancelled", "No-Show"])
    st.subheader("Availability grid (2-D: charger × hour)")
    grid = app.bookings.availability_grid(sid, gday.strftime("%Y-%m-%d"))
    df = pd.DataFrame(grid, index=[c_["charger_id"] for c_ in sid.chargers], columns=[f"{h:02d}" for h in range(24)])
    st.dataframe(df.replace({"Free": "·", "Booked": "█", "Maintenance": "✖"}), width="stretch")
    st.caption("· free   █ booked   ✖ maintenance")
    st.subheader("Bookings of this station")
    rows = app.bookings.list_bookings(station_id=sid.station_id, status=status)
    recent = [b for b in rows if b.start_time >= datetime.combine(gday, time(0)) - timedelta(days=3)]
    ordered, comps = app.bookings.sorted_by_start(recent)
    st.caption(f"{len(ordered)} bookings from 3 days before the chosen day; ordered by start time with Merge Sort ({comps} comparisons).")
    st.dataframe(pd.DataFrame([{"ID": b.booking_id, "Driver": b.driver_id, "Charger": b.charger_id, "Start": b.start_time,
                                "End": b.end_time, "Status": b.status} for b in ordered[:300]]), hide_index=True, width="stretch")

    if user.can("cancel_any"):
        st.subheader("Cancel any booking (administrator)")
        conf = [b for b in rows if b.status == "Confirmed" and b.end_time > app.now()]
        if conf:
            pick = st.selectbox("Booking", conf, format_func=lambda b: f"#{b.booking_id} {b.driver_id} {b.start_time:%d %b %H:%M}")
            if st.button("Cancel selected booking"):
                ok, res = run_action(app.cancel_booking, user, pick.booking_id)
                if ok:
                    flash("Booking cancelled.")
                    for req, nb in res[1]:
                        flash(f"Waiting driver {req['driver_id']} promoted to booking #{nb.booking_id}.", "info")
                    st.rerun()


TABS = []
if user.can("book"):
    TABS.append(("Book a charger", book_tab))
if user.driver_id:
    TABS.append(("My bookings", mine_tab))
if user.can("view_all_bookings"):
    TABS.append(("All bookings & availability", all_tab))
for (title, fn), tab in zip(TABS, st.tabs([t for t, _ in TABS])):
    with tab:
        fn()
