"""Keeps the login token in a browser cookie so a page refresh does not log the user out.

Streamlit can READ cookies (`st.context.cookies`) but not set them, so a zero-height HTML component runs a tiny
script that sets / clears the cookie. The cookie holds only a random opaque token; the server decides whether it is
still valid (services/login_session_service.py), so logout, expiry and password reset work server-side.
Limits: the cookie is set by JavaScript, so it cannot be HttpOnly; it is SameSite=Lax and Secure on https.
"""
from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components

COOKIE_NAME = "cs_session"


def read_cookie():
    try:
        return st.context.cookies.get(COOKIE_NAME)
    except Exception:                      # old Streamlit, tests, or no browser: just behave as "no cookie"
        return None


def _script(value: str, max_age: int) -> str:
    return f"""<script>
(function () {{
var p = window.parent, secure = (p.location.protocol === 'https:') ? '; Secure' : '';
var c = {json.dumps(COOKIE_NAME)} + '=' + {json.dumps(value)} + '; Max-Age={max_age}; Path=/; SameSite=Lax' + secure;
try {{ p.document.cookie = c; }} catch (e) {{ document.cookie = c; }}
}})();
</script>"""


def sync_cookie(max_age_seconds: int) -> None:
    """Emit the pending 'set' or 'clear' instruction (if any). Call once per run, near the top of app.py."""
    token = st.session_state.pop("_set_cookie", None)
    if token:
        components.html(_script(token, max_age_seconds), height=0)
    elif st.session_state.pop("_clear_cookie", False):
        components.html(_script("", 0), height=0)
