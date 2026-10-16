import streamlit as st

from ai.recommendation import Weights, recommend_stations
from analytics import charts as C
from core.state import get_app, get_data, require_page
from models.charger import ALL_CONNECTORS

user = require_page("recommend")
app, d = get_app(), get_data()
st.title("Smart Station Recommendation")
st.caption("Ranks stations for you and explains why. Rule-based and transparent: no black box. "
        "Wait times come from the booking history.")

c1, c2, c3 = st.columns(3)
veh = app.vehicle_of_driver(user.driver_id) if user.driver_id else None
if veh:
    connector = veh["connector"]
    c1.write(f"Your vehicle: **{veh['vehicle_model']}** → **{connector}**")
else:
    connector = c1.selectbox("Connector type", list(ALL_CONNECTORS))
area = c2.selectbox("Where are you? (area)", sorted(app.scheduler.distances))
hour = c3.slider("When do you want to charge? (hour)", 0, 23, 18)
max_km = c3.slider("Maximum distance (km)", 2, 40, 20, 1)
with st.expander("Adjust what matters to you (weights)"):
    w = st.columns(5)
    weights = Weights(
        distance=w[0].slider("Distance", 0.0, 1.0, 0.30, 0.05), wait=w[1].slider("Waiting", 0.0, 1.0, 0.30, 0.05),
        price=w[2].slider("Price", 0.0, 1.0, 0.15, 0.05), power=w[3].slider("Speed", 0.0, 1.0, 0.15, 0.05),
        availability=w[4].slider("Free now", 0.0, 1.0, 0.10, 0.05))
try:
    res = recommend_stations(d["stations"], d["chargers"], d["bookings"], area, connector, hour,
                            app.scheduler.distances, weights=weights, max_distance_km=float(max_km))
except ValueError as e:
    st.error(str(e))
    st.stop()

if res.ranked.empty:
    st.warning("No station matches your connector, hour and distance. Try a larger distance or another hour.")
else:
    best = res.ranked.iloc[0]
    st.success(f"**Best choice: {best['name']}** ({best['city']}) - score {best['score']}/100. {best['why']}")
    m = st.columns(4)
    m[0].metric("Distance", f"{best['distance_km']} km")
    m[1].metric("Expected wait", f"{best['expected_wait_min']:.0f} min", help=best["wait_basis"])
    m[2].metric("Price", f"{best['price_per_kwh']} EGP/kWh")
    m[3].metric("Fastest charger", f"{best['max_power_kw']:.0f} kW")
    st.plotly_chart(C.recommendation_breakdown(res.ranked), width="stretch")
    st.dataframe(res.ranked[["rank", "name", "score", "distance_km", "expected_wait_min", "price_per_kwh",
                            "max_power_kw", "free_now", "compatible_chargers", "why"]], hide_index=True, width="stretch")
if not res.excluded.empty:
    with st.expander(f"{len(res.excluded)} station(s) not shown - and why"):
        st.dataframe(res.excluded, hide_index=True, width="stretch")
st.caption("Estimates only. Availability uses the current charger status; wait uses the booking history. "
        "To book, open the Bookings page.")
