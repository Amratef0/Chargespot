"""Streamlit pages with a real login, on a copy of the FULL shipped data (read-only tests)."""
import shutil
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from services.auth_service import AuthService

ROOT = Path(__file__).resolve().parents[1]
CREDS = {"admin": ("admin@chargespot.com", "Admin1234"), "operator": ("operator@chargespot.com", "Operator1234"),
         "user": ("ahmed@gmail.com", "123456789")}


@pytest.fixture(scope="module")
def full_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("full") / "data"
    shutil.copytree(ROOT / "data", d, ignore=shutil.ignore_patterns("users.json", "waiting.csv"))
    mp = pytest.MonkeyPatch()
    mp.setenv("CHARGESPOT_DATA_DIR", str(d))
    st.cache_resource.clear()
    yield d
    mp.undo()
    st.cache_resource.clear()


def login_as(full_dir, role):
    return AuthService(full_dir / "users.json").login(*CREDS[role])


def page(full_dir, name, role="admin"):
    at = AppTest.from_file(str(ROOT / "pages" / f"{name}.py"), default_timeout=180)
    at.session_state["user"] = login_as(full_dir, role)
    return at.run()


# ----------------------------------------------------------------- every page for every role that may open it
MATRIX = [("0_Home", r) for r in CREDS] + [("1_Stations", r) for r in CREDS] + [("2_Bookings", r) for r in CREDS] + \
         [("3_Waiting_List", r) for r in CREDS] + [("4_Sessions", "operator"), ("4_Sessions", "admin")] + \
         [("5_Driver_Dashboard", "user"), ("5_Driver_Dashboard", "admin")] + \
         [("7_Recommendation", r) for r in CREDS] + [("6_Analytics", "admin")]


@pytest.mark.parametrize("name,role", MATRIX)
def test_page_runs_for_allowed_role(full_dir, name, role):
    assert not page(full_dir, name, role).exception


def test_driver_home_is_personal_not_the_network_dashboard(full_dir):
    at = page(full_dir, "0_Home", "user")
    labels = [m.label for m in at.metric]
    assert not at.exception and {"Next booking", "Energy charged", "Spent so far"} <= set(labels)
    assert "Stations" not in labels and "Bookings (history + live)" not in labels       # the admin's numbers


def test_operator_home_shows_operations(full_dir):
    labels = [m.label for m in page(full_dir, "0_Home", "operator").metric]
    assert {"Chargers available", "Active sessions", "Waiting list"} <= set(labels) and "Stations" not in labels


def test_admin_home_keeps_the_network_overview(full_dir):
    labels = [m.label for m in page(full_dir, "0_Home", "admin").metric]
    assert {"Stations", "Chargers", "Bookings (history + live)"} <= set(labels)


@pytest.mark.parametrize("name,role", [("6_Analytics", "operator"), ("6_Analytics", "user"),
                                       ("4_Sessions", "user")])
def test_permission_is_enforced_on_restricted_pages(full_dir, name, role):
    at = page(full_dir, name, role)
    assert not at.exception and at.error and "permission" in at.error[0].value


# ----------------------------------------------------------------- login / register screen
def shell(full_dir, user=None):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    if user:
        from core.state import get_app
        u = login_as(full_dir, user)
        at.session_state["user"] = u
        at.session_state["auth_token"] = get_app().login_sessions.create(u.email)     # a real server-side session
    return at.run()


def test_login_screen_when_nobody_is_logged_in(full_dir):
    at = shell(full_dir)
    assert not at.exception and [t.label for t in at.tabs] == ["Login", "Register", "Verify e-mail", "Forgot password"] and at.session_state["user"] is None


def test_login_success_and_wrong_password(full_dir):
    at = shell(full_dir)
    at.text_input[0].set_value("admin@chargespot.com"); at.text_input[1].set_value("wrong")
    at.button[0].click().run()
    assert at.error and "Incorrect" in at.error[0].value and at.session_state["user"] is None
    at.text_input[1].set_value("Admin1234")
    at.button[0].click().run()
    assert not at.exception and at.session_state["user"].role == "admin"


def test_register_form_shows_every_problem_at_once(full_dir):
    at = shell(full_dir)
    next(t for t in at.text_input if t.label == "Full name").set_value("ab")
    next(t for t in at.text_input if t.label == "Age").set_value("12")
    next(b for b in at.button if b.label == "Create account").click().run()
    assert not at.exception and at.error
    msg = at.error[0].value
    assert "Name" in msg and "Age" in msg and "National ID" in msg and "e-mail" in msg


def test_a_valid_token_restores_the_login_after_a_refresh(full_dir):
    from core.state import get_app
    token = get_app().login_sessions.create(login_as(full_dir, "admin").email)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.session_state["auth_token"] = token                  # what the cookie provides after F5; no `user` yet
    at.run()
    assert not at.exception and at.session_state["user"].role == "admin"


def test_a_revoked_token_shows_the_login_screen(full_dir):
    from core.state import get_app
    store = get_app().login_sessions
    token = store.create(login_as(full_dir, "admin").email)
    store.revoke(token)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.session_state["auth_token"] = token
    at.run()
    assert not at.exception and at.session_state["user"] is None and len(at.tabs) == 4


def test_logout_revokes_the_server_side_session(full_dir):
    from core.state import get_app
    at = shell(full_dir, "user")
    token = at.session_state["auth_token"]
    next(b for b in at.button if b.label == "Logout").click().run()
    assert not at.exception and at.session_state["user"] is None
    assert get_app().login_sessions.validate(token) is None


def test_forgot_password_screen_never_reveals_whether_an_account_exists(full_dir):
    at = shell(full_dir)
    next(t for t in at.text_input if t.label == "Account e-mail").set_value("nobody@nowhere.com")
    next(b for b in at.button if b.label == "Send reset code").click().run()
    assert not at.exception and any("If an account exists" in i.value for i in at.info)


@pytest.mark.parametrize("role", ["user", "operator", "admin"])
def test_shell_runs_for_every_role(full_dir, role):
    at = shell(full_dir, role)
    assert not at.exception and at.session_state["user"].role == role


# ----------------------------------------------------------------- analytics (adapted to the team's data)
def test_analytics_has_eight_tabs_and_team_data(full_dir):
    at = page(full_dir, "6_Analytics")
    assert len(at.tabs) == 8
    vals = {m.label: m.value for m in at.metric}
    assert int(vals["Bookings"].replace(",", "")) > 20000 and int(vals["🔴 High risk"]) >= 3 and int(vals["Chargers assessed"]) == 54


def test_analytics_messy_file_is_cleaned_with_exact_match(full_dir):
    at = page(full_dir, "6_Analytics")
    at.sidebar.radio[0].set_value("Raw messy file (auto-cleaned)").run()
    assert not at.exception and any("Every injected defect type was detected exactly" in s.value for s in at.success)


def test_analytics_filters_with_no_match_warn_instead_of_crash(full_dir):
    at = page(full_dir, "6_Analytics")
    at.sidebar.multiselect[0].set_value([]).run()
    assert not at.exception and at.warning


def test_analytics_search_demo_refuses_unsorted_input(full_dir):
    at = page(full_dir, "6_Analytics")
    at.text_input[0].set_value("5, 3, 9, 1").run()
    assert not at.exception and any("SORTED" in e.value for e in at.error)


def test_analytics_scheduling_tab_and_llm_checkbox(full_dir, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    at = page(full_dir, "6_Analytics")
    assert {"Cost saved vs FCFS", "Best strategy"} <= {m.label for m in at.metric}
    assert next(c for c in at.checkbox if "LLM" in c.label).disabled
    assert any("First-come-first-served" in m.value for m in at.markdown)


def test_analytics_forecast_button(full_dir):
    at = page(full_dir, "6_Analytics")
    next(b for b in at.button if b.label == "Train & forecast").click().run()
    assert not at.exception and any("Baseline" in df.value.to_string() for df in at.dataframe)


# ----------------------------------------------------------------- other pages with data
def test_recommendation_for_a_driver_names_a_best_station(full_dir):
    at = page(full_dir, "7_Recommendation", "user")
    assert at.success and "Best choice" in at.success[0].value


def test_recommendation_warns_when_nothing_is_close_enough(full_dir):
    at = page(full_dir, "7_Recommendation", "admin")
    next(s for s in at.selectbox if s.label.startswith("Connector")).set_value("CHAdeMO")
    next(s for s in at.slider if s.label.startswith("Maximum distance")).set_value(2)
    at.run()
    assert not at.exception and (at.warning or at.success)


def test_battery_monitor_validates_and_estimates(full_dir):
    at = page(full_dir, "5_Driver_Dashboard", "user")
    assert not at.exception and {"Estimated time to target", "Estimated range now"} <= {m.label for m in at.metric}
    next(n for n in at.number_input if n.label == "Target battery %").set_value(10).run()
    assert at.error and "Target" in at.error[0].value