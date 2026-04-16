"""
Q4 Dealer Scheme Gift Selection Portal — Entry Point

Streamlit multipage app with PIN-based authentication.
Run with: streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Q4 Dealer Scheme Portal",
    page_icon="🎁",
    layout="wide",
    initial_sidebar_state="expanded",
)

import auth  # noqa: E402


def init_session_state() -> None:
    """Initialize session state keys if they don't exist."""
    defaults = {
        "authenticated": False,
        "user_name": "",
        "role": "",
        "user_id": None,
        "failed_attempts": 0,
        "lockout_until": 0,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def show_login() -> None:
    """Render the PIN login screen."""
    st.markdown("## Q4 Dealer Scheme Portal")
    st.markdown("Enter your PIN to continue.")

    # Check lockout
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
            st.rerun()
        else:
            attempts = auth.record_failed_attempt(st.session_state)
            remaining_attempts = auth.MAX_ATTEMPTS - attempts
            if remaining_attempts > 0:
                st.error(f"Invalid PIN. {remaining_attempts} attempt(s) remaining.")
            else:
                st.error(f"Too many failed attempts. Locked for {auth.LOCKOUT_SECONDS} seconds.")
                st.rerun()


def show_sidebar() -> None:
    """Render the authenticated sidebar with user info and logout."""
    with st.sidebar:
        st.markdown(f"**{st.session_state['user_name']}**")
        role_label = "Admin" if st.session_state["role"] == "admin" else "Sales/Territory Manager"
        st.caption(role_label)
        st.divider()

        if st.button("Logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


def show_home() -> None:
    """Render the home page after successful login."""
    st.markdown("## Q4 Dealer Scheme Portal")
    st.markdown("Welcome! Use the sidebar to navigate.")

    if st.session_state["role"] == "admin":
        st.info("You have **Admin** access. You can view both Gift Selection and Consolidated Admin pages.")
    else:
        st.info("Navigate to **Gift Selection** in the sidebar to manage retailer gift redemptions.")


def main() -> None:
    init_session_state()

    if not st.session_state["authenticated"]:
        show_login()
        st.stop()

    show_sidebar()
    show_home()


if __name__ == "__main__":
    main()
