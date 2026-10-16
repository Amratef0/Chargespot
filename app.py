import os

import streamlit as st

from core.state import authenticate, get_app, login_user, logout_user, sync_cookie
from core.ui import run_action, show_flash
from models.exceptions import ChargeSpotError, EmailNotVerifiedError
from services.authz import allowed_pages
from services.mailer import FileMailer

st.set_page_config(page_title="ChargeSpot", layout="wide")
app = get_app()
user = authenticate()
sync_cookie()


def link_actions():
    """Links from e-mails: ?verify=<token> is checked right away; ?reset=<token> opens the new-password form."""
    qp = st.query_params
    if qp.get("verify"):
        ok, _ = run_action(app.auth.verify_email, qp.get("verify"),
                        success="E-mail verified. You can log in now.")
        del qp["verify"]
    reset = qp.get("reset")
    if reset:
        st.subheader("Choose a new password")
        with st.form("reset_link"):
            p1 = st.text_input("New password (min 8)", type="password")
            p2 = st.text_input("Confirm new password", type="password")
            if st.form_submit_button("Change password"):
                ok, _ = run_action(app.auth.reset_password, reset, p1, p2,
                                success="Password changed. You can log in now.")
                if ok:
                    del qp["reset"]
                    st.rerun()
        return True
    return False


def dev_mailbox_note():
    if isinstance(app.mailer, FileMailer):
        if os.environ.get("CHARGESPOT_DEV_MAILBOX") == "1":
            with st.expander("Development mailbox (SMTP is not configured)"):
                for m in app.mailer.latest(5) or ["No messages yet."]:
                    st.code(m)
        else:
            st.caption("E-mail sending is not configured on this server, so verification and reset e-mails "
                    "cannot be delivered.")


def auth_screen():
    st.title("ChargeSpot")
    st.caption("EV charging: find a charger, book a slot, join the waiting list, track your sessions. \n\n")
    show_flash()
    if link_actions():
        return
    tab_in, tab_reg, tab_ver, tab_forgot = st.tabs(["Login", "Register", "Verify e-mail", "Forgot password"])
    with tab_in:
        with st.form("login"):
            email = st.text_input("E-mail")
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                try:
                    login_user(app.auth.login(email, pw))
                    st.session_state.pop("unverified_email", None)
                    st.rerun()
                except EmailNotVerifiedError as e:
                    st.session_state["unverified_email"] = email
                    st.error(str(e))
                except ChargeSpotError as e:
                    st.error(str(e))
        pending = st.session_state.get("unverified_email")
        if pending and st.button("Send a new verification e-mail"):
            app.auth.resend_verification(pending)
            st.info("If that account is waiting for verification, a new e-mail is on its way.")
    with tab_reg:
        with st.form("register"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Full name")
            email = c2.text_input("E-mail ")
            phone = c1.text_input("Phone")
            age = c2.text_input("Age")
            gender = c1.selectbox("Gender", ["male", "female"])
            gov = c2.text_input("Governorate")
            nid = c1.text_input("National ID (14 digits)")
            veh = c2.selectbox("Your vehicle", list(app.vehicles["vehicle_model"]))
            pw1 = c1.text_input("Password (min 8)", type="password")
            pw2 = c2.text_input("Confirm password", type="password")
            if st.form_submit_button("Create account"):
                ok, new = run_action(app.auth.register, name, email, phone, age, gender, gov, nid, pw1, pw2, veh)
                if ok:
                    if new.verification_sent:
                        st.success(f"Account created. Your driver ID is {new.driver_id}. We sent a verification "
                                f"e-mail to {new.email}: open the link (or paste the code in the 'Verify e-mail' "
                                "tab), then log in.")
                    elif new.verification_sent is False:
                        st.warning(f"Account created (driver ID {new.driver_id}) but the verification e-mail could "
                                    f"not be sent. Use 'Verify e-mail' > 'Send a new code' in a few minutes.")
                    else:
                        st.success(f"Account created. Your driver ID is {new.driver_id}. You can log in now.")
    with tab_ver:
        st.caption("Paste the code from your verification e-mail (or just open the link in the e-mail).")
        with st.form("verify"):
            code = st.text_input("Verification code")
            if st.form_submit_button("Verify e-mail"):
                run_action(app.auth.verify_email, code, success="E-mail verified. You can log in now.")
        with st.form("resend"):
            who = st.text_input("E-mail address ", key="resend_email")
            if st.form_submit_button("Send a new code"):
                app.auth.resend_verification(who)
                st.info("If that address has an account waiting for verification, a new e-mail is on its way.")
    with tab_forgot:
        st.caption("Step 1: we e-mail you a single-use code that works for 30 minutes.")
        with st.form("forgot"):
            who = st.text_input("Account e-mail", key="forgot_email")
            if st.form_submit_button("Send reset code"):
                app.auth.request_password_reset(who)
                st.info("If an account exists for that address, a reset e-mail is on its way.")
        st.caption("Step 2: paste the code and choose a new password.")
        with st.form("reset"):
            code = st.text_input("Reset code")
            p1 = st.text_input("New password (min 8)", type="password", key="reset_p1")
            p2 = st.text_input("Confirm new password", type="password", key="reset_p2")
            if st.form_submit_button("Change password"):
                run_action(app.auth.reset_password, code, p1, p2, success="Password changed. You can log in now.")
    dev_mailbox_note()


if user is None:
    # Always call st.navigation, even logged out: without it Streamlit lists every file in pages/ in the sidebar
    # (and serves them by URL). A single hidden "page" = login screen, no sidebar, nothing else reachable.
    st.navigation([st.Page(auth_screen, title="Login")], position="hidden").run()
    st.stop()

PAGES = {
    "home": st.Page("pages/0_Home.py", title="Home", icon="🏠", default=True),
    "stations": st.Page("pages/1_Stations.py", title="Stations & Chargers", icon="🔌"),
    "bookings": st.Page("pages/2_Bookings.py", title="Bookings", icon="📅"),
    "waiting": st.Page("pages/3_Waiting_List.py", title="Waiting List", icon="⏳"),
    "sessions": st.Page("pages/4_Sessions.py", title="Charging Sessions", icon="🔋"),
    "driver": st.Page("pages/5_Driver_Dashboard.py", title="Driver Dashboard", icon="🚗"),
    "recommend": st.Page("pages/7_Recommendation.py", title="Smart Recommendation", icon="🎯"),
    "analytics": st.Page("pages/6_Analytics.py", title="Admin Analytics", icon="📊"),
}

with st.sidebar:
    st.title("ChargeSpot")
    st.markdown(f"**{user.name}**  \n{user.label}" + (f" · `{user.driver_id}`" if user.driver_id else ""))
    if st.button("Logout"):
        logout_user()
        st.rerun()
    st.caption("🌗 Theme: ⋮ menu (top right) → Settings → Theme")

# the menu is DERIVED from permissions (services/authz.py): there is no second list of roles to keep in sync
st.navigation([PAGES[k] for k in allowed_pages(user, PAGES)]).run()