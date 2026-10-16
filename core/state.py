
from __future__ import annotations

import os

import streamlit as st

from core import browser_session
from core.app_context import ChargeSpotApp
from core.data_store import DATA_DIR
from core.ui import flash
from services.authz import can_open


@st.cache_resource(show_spinner="Loading ChargeSpot data...")
def get_app() -> ChargeSpotApp:
    return ChargeSpotApp(os.environ.get("CHARGESPOT_DATA_DIR") or DATA_DIR)


def init_state() -> None:
    st.session_state.setdefault("user", None)
    st.session_state.setdefault("auth_token", None)
    st.session_state.setdefault("chat", [])


def current_user():
    init_state()
    return st.session_state["user"]


def get_data() -> dict:
    """All tables as DataFrames (cached until the next change)."""
    return get_app().frames()


def reload_data() -> None:
    get_app().reload_from_disk(current_user())          # administrators only (checked in the application layer)


def authenticate():
    """Who is logged in RIGHT NOW? Call first in app.py, on every run.

    The token (session_state, else the browser cookie) must still be valid on the server; the user is re-read
    from the user file so a changed role applies immediately. Returns the User or None."""
    init_state()
    app = get_app()
    had_user = st.session_state["user"] is not None
    token = st.session_state["auth_token"] or browser_session.read_cookie()
    email = app.login_sessions.validate(token) if token else None
    user = app.auth.get_user(email) if email else None
    if user is None:
        if token:
            st.session_state["_clear_cookie"] = True                    # drop a stale cookie
        if had_user:
            flash("Your session has ended. Please log in again.", "warning")
        st.session_state.update(user=None, auth_token=None)
        return None
    st.session_state.update(user=user, auth_token=token)
    return user


def login_user(user) -> None:
    """Start a server-side login session for an already-authenticated user."""
    token = get_app().login_sessions.create(user.email)
    st.session_state.update(user=user, auth_token=token, _set_cookie=token)


def logout_user() -> None:
    get_app().login_sessions.revoke(st.session_state.get("auth_token"))
    st.session_state.update(user=None, auth_token=None, chat=[], _clear_cookie=True)


def sync_cookie() -> None:
    browser_session.sync_cookie(get_app().login_sessions.max_age_seconds)


def require(permission: str):
    """Stop the page with a clear message unless the logged-in user has `permission`."""
    user = current_user()
    if user is None or not user.can(permission):
        st.error("You do not have permission to open this page.")
        st.stop()
    return user


def require_page(page_key: str):
    """Page guard: the same PAGE_ACCESS table that builds the sidebar decides here (defence in depth)."""
    user = current_user()
    if user is None:
        st.error("Please log in first.")
        st.stop()
    if not can_open(user, page_key):
        st.error("You do not have permission to open this page.")
        st.stop()
    return user
