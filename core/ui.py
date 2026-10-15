"""Small shared UI helpers."""
import streamlit as st

from models.exceptions import ChargeSpotError


def run_action(fn, *args, success=None, **kwargs):
    """Run a service call; show a friendly error for ChargeSpotError. Returns (ok, result)."""
    try:
        res = fn(*args, **kwargs)
    except ChargeSpotError as e:
        st.error(str(e))
        return False, None
    except ValueError as e:                       # Member 3's services raise ValueError for bad numbers
        st.error(str(e))
        return False, None
    if success:
        st.success(success(res) if callable(success) else success)
    return True, res


def flash(message: str, kind: str = "success") -> None:
    """Remember a message across st.rerun() (a message shown right before a rerun would vanish)."""
    st.session_state.setdefault("_flash", []).append((kind, message))


def show_flash() -> None:
    for kind, message in st.session_state.pop("_flash", []):
        getattr(st, kind)(message)
