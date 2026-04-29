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
from views.dealer_details import render_dealer_details  # noqa: E402
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


_VIEW_TITLES = {
    "gift_selection": "Gift Selection",
    "dealer_details": "Dealer Details",
    "admin": "Admin Dashboard",
}


def render_top_bar() -> None:
    """Inline top bar: title, user, nav tabs, logout."""
    is_admin = st.session_state["role"] == "admin"
    view = st.session_state.get("view", "gift_selection")
    title = _VIEW_TITLES.get(view, "Gift Selection")

    header_cols = st.columns([5, 2, 1])
    with header_cols[0]:
        st.markdown(f"### {title}")
    with header_cols[1]:
        role_label = "Admin" if is_admin else "Sales/Territory Manager"
        st.caption(f"**{st.session_state['user_name']}** · {role_label}")
    with header_cols[2]:
        if st.button("Logout", use_container_width=True, key="logout_btn"):
            _logout()

    nav_targets = [
        ("gift_selection", "Gift Selection"),
        ("dealer_details", "Dealer Details"),
    ]
    if is_admin:
        nav_targets.append(("admin", "Admin Dashboard"))

    nav_cols = st.columns(len(nav_targets))
    for col, (target, label) in zip(nav_cols, nav_targets):
        with col:
            is_current = view == target
            if st.button(
                ("● " + label) if is_current else label,
                use_container_width=True,
                key=f"nav_{target}",
                disabled=is_current,
            ):
                st.session_state["view"] = target
                st.rerun()

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
    elif view == "dealer_details":
        render_dealer_details()
    else:
        render_gift_selection()


if __name__ == "__main__":
    main()
