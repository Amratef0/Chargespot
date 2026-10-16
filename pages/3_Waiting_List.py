"""Waiting list (Member 2): FIFO queue with positions; automatic promotion happens on cancel/complete."""
import pandas as pd
import streamlit as st

from core.state import get_app, require_page
from core.ui import flash, run_action, show_flash

user = require_page("waiting")
app = get_app()
app.waiting.purge_expired(app.now())
st.title("Waiting List")
show_flash()
names = {s.station_id: s.name for s in app.stations.stations}
q = app.waiting.queue
st.metric("Drivers waiting", len(q))
nxt = q.peek()
if nxt:
    st.caption(f"Next in line (head of the queue): request #{nxt['request_id']} for {names.get(nxt['station_id'], '?')} "
            f"at {nxt['start_time']:%d %b %H:%M}.")

if user.driver_id:
    st.subheader("My waiting requests")
    mine = app.waiting.requests_for_driver(user.driver_id)
    if not mine:
        st.info("You are not waiting for anything.")
    else:
        st.dataframe(pd.DataFrame([{"Request": r["request_id"], "Position": pos, "Station": names.get(r["station_id"]),
                                    "Wanted time": r["start_time"], "Minutes": r["duration_min"]} for pos, r in mine]),
                    hide_index=True, width="stretch")
        sel = st.selectbox("Cancel a request", [r for _, r in mine], format_func=lambda r: f"#{r['request_id']}")
        if st.button("Cancel waiting request"):
            ok, _ = run_action(app.cancel_waiting, user, sel["request_id"])
            if ok:
                flash("Waiting request cancelled.")
                st.rerun()

if user.can("manage_waiting"):
    st.subheader("Whole queue (operator / admin)")
    items = list(q)
    if not items:
        st.info("The waiting list is empty.")
    else:
        st.dataframe(pd.DataFrame([{"Position": i + 1, "Request": r["request_id"], "Driver": r["driver_id"],
                                    "Station": names.get(r["station_id"]), "Connector": r["connector"],
                                    "Wanted time": r["start_time"], "Minutes": r["duration_min"],
                                    "Waiting since": r["created_at"]} for i, r in enumerate(items)]),
                    hide_index=True, width="stretch")
        sel = st.selectbox("Remove a request", items, format_func=lambda r: f"#{r['request_id']} ({r['driver_id']})", key="adm")
        if st.button("Remove request"):
            ok, _ = run_action(app.cancel_waiting, user, sel["request_id"])
            if ok:
                flash("Request removed.")
                st.rerun()