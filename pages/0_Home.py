import streamlit as st

from analytics import metrics as M
from core.state import get_app, get_data, reload_data, require_page

user = require_page("home")
app, d = get_app(), get_data()
st.title("ChargeSpot")
k = M.kpi_summary(d["bookings"], d["sessions"], d["chargers"], d["stations"])
c = st.columns(4)
c[0].metric("Stations", len(d["stations"]))
c[1].metric("Chargers", len(d["chargers"]))
c[2].metric("Bookings (history + live)", f"{k['total_bookings']:,}")
c[3].metric("Waiting list now", len(app.waiting.queue))

st.subheader("Charger status right now")
snap = d["chargers"]["status"].value_counts().rename_axis("status").reset_index(name="chargers")
a, b = st.columns([1, 2])
a.dataframe(snap, hide_index=True, width="stretch")
b.bar_chart(snap, x="status", y="chargers")
if user.can("analytics") and st.button("Reload data from disk"):
    reload_data()
    st.rerun()
