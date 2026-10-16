import streamlit as st



def is_named(error: BaseException, class_name: str) -> bool:
    return any(c.__name__ == class_name for c in type(error).__mro__)


def is_app_error(error: BaseException) -> bool:
    return is_named(error, "ChargeSpotError") or isinstance(error, ValueError)   # M3's services raise ValueError


def run_action(fn, *args, success=None, **kwargs):
    """Run a service call; show a friendly error for ChargeSpotError. Returns (ok, result)."""
    try:
        res = fn(*args, **kwargs)
    except Exception as e:                        # st.rerun()/st.stop() are BaseException: they pass through
        if not is_app_error(e):
            raise
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