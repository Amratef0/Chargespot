
"""Stations & chargers (Member 1's module: search, filters, availability, admin actions, undo)."""
import pandas as pd
import streamlit as st

from core.state import get_app, require_page
from core.ui import run_action
from models.charger import ACCharger, DCCharger, CHARGER_STATUSES
from services.station_service import StationService

user = require_page("stations")
app = get_app()
svc = app.stations

st.title("Stations & Chargers")

# Admin sees both tabs; Driver and Operator see Find stations only.
if user.role == "admin":
    tab_find, tab_manage = st.tabs(["Find stations", "Manage"])
else:
    tab_find = st.container()
    tab_manage = None

with tab_find:
    c = st.columns(5)

    name = c[0].text_input("Name contains (sequential search)")
    gov = c[1].selectbox(
        "Governorate",
        [None] + sorted({s.governorate for s in svc.stations})
    )
    conn = c[2].selectbox("Connector", [None, "Type 2", "CCS2", "CHAdeMO"])
    status = c[3].selectbox(
        "Has charger with status",
        [None, *CHARGER_STATUSES]
    )
    min_kw = c[4].number_input("Min power (kW)", 0, 500, 0, 10)

    found = svc.search(name, gov, conn, status, min_kw or None)
    rows = []

    for s in found:
        a = s.get_availability_summary()
        rows.append({
            "ID": s.station_id,
            "Station": s.name,
            "Governorate": s.governorate,
            "Area": s.area,
            "Address": s.address,
            "Chargers": a["total"],
            "Available": a["available"],
            "Occupied": a["occupied"],
            "Maintenance": a["maintenance"],
            "EGP/kWh": s.price_per_kwh
        })

    st.caption(f"{len(rows)} station(s) found")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    if found:
        pick = st.selectbox(
            "Show chargers of",
            found,
            format_func=lambda s: f"{s.station_id} - {s.name}"
        )

        st.write("**Chargers**")
        for ch in StationService.charger_objects(pick):
            st.text(ch.get_info())

        pts = pd.DataFrame([
            {"lat": s.lat, "lon": s.lon}
            for s in found
            if s.lat is not None
        ])

        if not pts.empty:
            st.map(pts, latitude="lat", longitude="lon")
            st.caption("Map positions are approximate (display only).")


# Manage tab is created only for administrators.
if tab_manage is not None:
    with tab_manage:
        st.subheader("Change charger status")

        st_pick = st.selectbox(
            "Station",
            svc.stations,
            format_func=lambda s: f"{s.station_id} - {s.name}",
            key="m_station"
        )

        if st_pick.chargers:
            cid = st.selectbox(
                "Charger",
                [c["charger_id"] for c in st_pick.chargers]
            )
            new = st.selectbox("New status", CHARGER_STATUSES)

            if st.button("Update status"):
                run_action(
                    app.update_charger_status,
                    user,
                    st_pick,
                    cid,
                    new,
                    success="Status updated."
                )

        if user.can("manage_stations"):
            st.divider()
            st.subheader("Add / remove chargers (administrator)")

            c = st.columns(4)
            ctype = c[0].selectbox("Type", ["AC", "DC"])
            new_id = c[1].text_input("Charger ID (AC-xxx / DC-xxx)")
            kw = c[2].number_input("Power (kW)", 1, 500, 22)
            cn = c[3].selectbox(
                "Connector",
                ["Type 2"] if ctype == "AC" else ["CCS2", "CHAdeMO"]
            )

            if st.button("Add charger"):
                def add():
                    obj = (
                        ACCharger if ctype == "AC" else DCCharger
                    )(new_id.strip(), kw, cn)
                    return app.add_charger(user, st_pick.station_id, obj)

                run_action(add, success="Charger added.")

            if st_pick.chargers:
                rm = st.selectbox(
                    "Charger to remove",
                    [c["charger_id"] for c in st_pick.chargers],
                    key="rm"
                )

                if st.button("Remove charger"):
                    run_action(
                        app.remove_charger,
                        user,
                        st_pick,
                        rm,
                        success="Charger removed (you can undo this)."
                    )

            st.subheader("Add / edit / remove stations (administrator)")

            with st.expander("Add a station"):
                f = st.columns(4)
                sid = f[0].text_input("Station ID (number)")
                sname = f[1].text_input("Name")
                sgov = f[2].text_input("Governorate")
                saddr = f[3].text_input("Address")

                if st.button("Add station"):
                    run_action(
                        app.add_station,
                        user,
                        sid.strip(),
                        sname,
                        sgov,
                        saddr,
                        success="Station added."
                    )

            with st.expander("Edit or remove the selected station"):
                new_price = st.number_input(
                    "Price per kWh (EGP)",
                    0.5,
                    50.0,
                    float(st_pick.price_per_kwh),
                    0.5
                )

                if st.button("Save price"):
                    run_action(
                        app.edit_station,
                        user,
                        st_pick.station_id,
                        price_per_kwh=new_price,
                        success="Station updated."
                    )

                if st.button("Remove this station"):
                    run_action(
                        app.remove_station,
                        user,
                        st_pick.station_id,
                        success="Station removed (you can undo this)."
                    )

            st.divider()

            n = len(svc.admin_stack.stack)
            st.write(
                f"**Undo stack:** {n} change(s) can be undone. Last: "
                f"`{svc.admin_stack.peek()['action'] if n else '-'}`"
            )

            if st.button("↩️ Undo last admin change", disabled=n == 0):
                ok, msg = run_action(app.undo_last_admin_action, user)
                if ok and msg:
                    st.success(msg)
