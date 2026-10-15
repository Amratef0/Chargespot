"""Full user journeys THROUGH the Streamlit pages (data is written to a private temp folder)."""
from datetime import datetime, time, timedelta
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from services.auth_service import AuthService

ROOT = Path(__file__).resolve().parents[1]
CREDS = {"admin": ("admin@chargespot.com", "Admin1234"), "operator": ("operator@chargespot.com", "Operator1234"),
         "user": ("ahmed@gmail.com", "123456789")}
TOMORROW = datetime.combine(datetime.now().date() + timedelta(days=1), time(10, 0))


@pytest.fixture()
def env(data_dir, monkeypatch):
    monkeypatch.setenv("CHARGESPOT_DATA_DIR", str(data_dir))
    st.cache_resource.clear()
    yield data_dir
    st.cache_resource.clear()


def run(env, name, role, **state):
    at = AppTest.from_file(str(ROOT / "pages" / f"{name}.py"), default_timeout=120)
    at.session_state["user"] = AuthService(env / "users.json").login(*CREDS[role])
    for k, v in state.items():
        at.session_state[k] = v
    return at.run()


def vehicle_connector(env):
    veh = pd.read_csv(env / "drivers.csv").set_index("driver_id").loc["D101", "connector"]
    return veh


def book_via_ui(env):
    at = run(env, "2_Bookings", "user", booking_search={"area": "Nasr City", "connector": vehicle_connector(env),
                                                         "duration": 60, "start": TOMORROW})
    assert not at.exception
    next(b for b in at.button if b.label == "✅ Confirm booking").click().run()
    assert not at.exception and any("confirmed" in s.value for s in at.success), [e.value for e in at.error]
    return pd.read_csv(env / "bookings.csv", dtype=str).iloc[-1]


def test_driver_books_through_the_page_and_it_is_saved(env):
    row = book_via_ui(env)
    assert row["driver_id"] == "D101" and row["status"] == "Confirmed" and row["start_time"] == TOMORROW.strftime("%Y-%m-%d %H:%M")


def test_driver_cancels_through_the_page(env):
    row = book_via_ui(env)
    at = run(env, "2_Bookings", "user")
    next(b for b in at.button if b.label == "Cancel this booking").click().run()
    assert not at.exception and any("cancelled" in s.value.lower() for s in at.success)
    last = pd.read_csv(env / "bookings.csv", dtype=str).set_index("booking_id").loc[row["booking_id"]]
    assert last["status"] == "Cancelled"


def test_operator_starts_and_completes_a_session_through_the_page(env):
    row = book_via_ui(env)
    at = run(env, "4_Sessions", "operator")
    at.date_input[0].set_value(TOMORROW.date()).run()
    next(b for b in at.button if b.label == "▶️ Start session").click().run()
    assert not at.exception and not at.error, [e.value for e in at.error]
    at = run(env, "4_Sessions", "operator")                       # a fresh browser tab: the session is still Active
    assert any("Active sessions" in m.value for m in at.subheader)
    next(b for b in at.button if b.label == "⏹ Complete session").click().run()
    assert not at.exception and any("Completed" in s.value for s in at.success), [e.value for e in at.error]
    sess = pd.read_csv(env / "sessions.csv", dtype=str).iloc[-1]
    booking = pd.read_csv(env / "bookings.csv", dtype=str).set_index("booking_id").loc[row["booking_id"]]
    assert sess["booking_id"] == row["booking_id"] and booking["status"] == "Completed" and float(sess["energy_kwh"]) > 0


def test_admin_adds_a_charger_then_undoes_it(env):
    at = run(env, "1_Stations", "admin")
    assert not at.exception
    next(t for t in at.text_input if t.label == "Charger ID (AC-xxx / DC-xxx)").set_value("AC-777")
    next(b for b in at.button if b.label == "Add charger").click().run()
    assert not at.exception and any("added" in s.value for s in at.success), [e.value for e in at.error]
    assert "AC-777" in (env / "stations.json").read_text()
    at = run(env, "1_Stations", "admin")
    next(b for b in at.button if b.label.startswith("↩️ Undo")).click().run()
    assert not at.exception and any("Undid" in s.value for s in at.success)
    assert "AC-777" not in (env / "stations.json").read_text()


def test_admin_gets_a_friendly_error_for_a_bad_charger_id(env):
    at = run(env, "1_Stations", "admin")
    next(t for t in at.text_input if t.label == "Charger ID (AC-xxx / DC-xxx)").set_value("oops")
    next(b for b in at.button if b.label == "Add charger").click().run()
    assert not at.exception and at.error and "Invalid charger ID" in at.error[0].value


def test_driver_joins_waiting_list_and_sees_position(env):
    from core.app_context import ChargeSpotApp
    conn = vehicle_connector(env)
    prep = ChargeSpotApp(env)                                   # separate app: only used to fill the station on disk
    other = prep.auth.register("Other Driver", "other@mail.com", "01234567890", "30", "male", "cairo",
                               "30001010100001", "Password1", "Password1", "BYD Atto 3")
    for option in prep.find_station_options("Nasr City", conn, TOMORROW, 60):       # block EVERY reachable station
        while prep.book_at_station(other, option["station"], conn, TOMORROW, 60)["status"] == "confirmed":
            pass                                                # every compatible charger is now booked at 10:00
    st.cache_resource.clear()
    at = run(env, "2_Bookings", "user", booking_search={"area": "Nasr City", "connector": conn, "duration": 60,
                                                         "start": TOMORROW})
    assert not at.exception
    next(b for b in at.button if b.label.startswith("⏳ Join the waiting list")).click().run()
    assert not at.exception and any("waiting list" in s.value for s in at.success), [e.value for e in at.error]
    wl = run(env, "3_Waiting_List", "user")
    assert any("Position" in list(df.value.columns) for df in wl.dataframe)
    assert len(pd.read_csv(env / "waiting.csv")) == 1
