"""
Q4 Dealer Scheme Gift Selection Portal — Entry Point

Single-page Streamlit app with PIN-based auth.
Login → Gift Selection (default). Admins can toggle to Admin Dashboard.
Run with: streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Q4 Dealer Scheme Portal",
    page_icon="🎁",
    layout="wide",
    initial_sidebar_state="collapsed",
)

import auth  # noqa: E402
from views.admin import render_admin  # noqa: E402
from views.gift_selection import render_gift_selection  # noqa: E402


def init_session_state() -> None:
    defaults = {
        "authenticated": False,
        "user_name": "",
        "role": "",
        "user_id": None,
        "failed_attempts": 0,
        "lockout_until": 0,
        "view": "gift_selection",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def show_login() -> None:
    st.markdown("## Q4 Dealer Scheme Portal")
    st.markdown("Enter your PIN to continue.")

    locked, remaining = auth.is_locked_out(st.session_state)
    if locked:
        st.error(f"Too many failed attempts. Please wait {remaining} seconds.")
        st.stop()

    with st.form("login_form"):
        pin = st.text_input(
            "PIN",
            type="password",
            max_chars=6,
            placeholder="Enter 4-6 digit PIN",
        )
        submitted = st.form_submit_button("Login", use_container_width=True)

    if submitted:
        if not pin:
            st.warning("Please enter your PIN.")
            return

        user = auth.verify_pin(pin)
        if user:
            auth.reset_attempts(st.session_state)
            st.session_state["authenticated"] = True
            st.session_state["user_name"] = user["name"]
            st.session_state["role"] = user["role"]
            st.session_state["user_id"] = user["id"]
            st.session_state["view"] = "gift_selection"
            st.rerun()
        else:
            attempts = auth.record_failed_attempt(st.session_state)
            remaining_attempts = auth.MAX_ATTEMPTS - attempts
            if remaining_attempts > 0:
                st.error(f"Invalid PIN. {remaining_attempts} attempt(s) remaining.")
            else:
                st.error(f"Too many failed attempts. Locked for {auth.LOCKOUT_SECONDS} seconds.")
                st.rerun()


def render_top_bar() -> None:
    """Inline top bar: title, user, view switch (admin only), logout."""
    is_admin = st.session_state["role"] == "admin"
    view = st.session_state.get("view", "gift_selection")

    title = "Admin Dashboard" if view == "admin" else "Gift Selection"

    if is_admin:
        cols = st.columns([3, 2, 2, 1])
    else:
        cols = st.columns([5, 2, 1])

    with cols[0]:
        st.markdown(f"### {title}")

    if is_admin:
        with cols[1]:
            role_label = "Admin"
            st.caption(f"**{st.session_state['user_name']}** · {role_label}")
        with cols[2]:
            if view == "admin":
                if st.button("← Gift Selection", use_container_width=True, key="nav_gift"):
                    st.session_state["view"] = "gift_selection"
                    st.rerun()
            else:
                if st.button("Admin Dashboard →", use_container_width=True, key="nav_admin"):
                    st.session_state["view"] = "admin"
                    st.rerun()
        with cols[3]:
            if st.button("Logout", use_container_width=True, key="logout_btn"):
                _logout()
    else:
        with cols[1]:
            st.caption(f"**{st.session_state['user_name']}** · Sales/Territory Manager")
        with cols[2]:
            if st.button("Logout", use_container_width=True, key="logout_btn"):
                _logout()

    st.divider()


def _logout() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


def main() -> None:
    init_session_state()

    if not st.session_state["authenticated"]:
        show_login()
        st.stop()

    render_top_bar()

    view = st.session_state.get("view", "gift_selection")
    if view == "admin" and st.session_state["role"] == "admin":
        render_admin()
    else:
        render_gift_selection()


if __name__ == "__main__":
    main()
