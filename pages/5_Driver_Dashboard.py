import pandas as pd
import streamlit as st

from core.state import get_app, require_page
from core.ui import run_action
from models.exceptions import ChargeSpotError, InvalidBatteryValueError

user = require_page("driver")
app = get_app()
st.title("Driver Dashboard")
requested = None
if user.can("view_any_driver"):
    st.info("Pick a driver to look at (administrator view).")
    requested = st.selectbox("Driver", list(app.history_drivers["driver_id"]))
try:
    did = app.resolve_driver_id(user, requested)          # own data always; other drivers only with permission
except ChargeSpotError as e:
    st.error(str(e))
    st.stop()
veh = app.vehicle_of_driver(did)
st.caption(f"Driver **{did}** · vehicle **{veh['vehicle_model'] if veh else '-'}**")

st.subheader("Battery monitor")
st.caption("ESTIMATES from the values you enter. This app has no live connection to your car.")
if veh:
    c = st.columns(3)
    cur = c[0].number_input("Current battery %", 0.0, 100.0, 25.0, 1.0)
    tgt = c[1].number_input("Target battery %", 0.0, 100.0, 80.0, 1.0)
    kw = c[2].selectbox("Charger power (kW)", [7, 11, 22, 50, 60, 100, 120, 150], index=3)
    try:
        est = app.battery_for(did).calculate_estimates(cur, tgt, kw)
        m = st.columns(3)
        m[0].metric("Estimated time to target", f"{est['estimated_time_hours'] * 60:.0f} min")
        m[1].metric("Estimated range now", f"{est['estimated_range_km']:.0f} km")
        m[2].metric("Energy needed", f"{est['energy_needed_kwh']} kWh")
        if est["low_battery_warning"]:
            st.error("⚠️ Low battery (below 20%) - charge soon. See Smart Recommendation for the best station.")
    except InvalidBatteryValueError as e:
        st.error(str(e))

st.subheader("My upcoming bookings and waiting requests")
upcoming = [b for b in app.bookings.list_bookings(driver_id=did, status="Confirmed") if b.end_time > app.now()]
st.dataframe(pd.DataFrame([{"Booking": b.booking_id, "Station": b.station_name, "Charger": b.charger_id,
                            "Start": b.start_time, "End": b.end_time} for b in upcoming]), hide_index=True, width="stretch")
for pos, r in app.waiting.requests_for_driver(did):
    st.info(f"Waiting request #{r['request_id']}: position **{pos}** in the queue for {r['start_time']:%d %b %H:%M}.")

st.subheader("Session history")
key = st.selectbox("Sort by", ["start_time", "duration", "energy"])
sess = app.sessions.filter_sessions(user_id=did)
ordered, comps = app.sessions.sort_session_history(key, True, sess)
st.caption(f"{len(ordered)} sessions · Merge Sort, {comps} comparisons")
st.dataframe(pd.DataFrame([{"Session": s.session_id, "Charger": s.charger_id, "Planned start": s.planned_start,
                            "Actual start": s.start_time, "Minutes": s.duration_minutes, "kWh": s.energy_delivered_kwh}
                        for s in ordered[:100]]), hide_index=True, width="stretch")
