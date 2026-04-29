"""Dealer Details view — capture delivery contact info for each dealer.

Cascading filters: Zone -> State -> Distributor -> Dealer.
Once a dealer is picked, an editable form captures contact name, phone,
email and delivery address.
"""

from __future__ import annotations

import re

import pandas as pd
import streamlit as st

import db


_PHONE_RE = re.compile(r"^[0-9+\-\s()]{7,20}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


_FILTER_KEYS = (
    "dd_filter_zones",
    "dd_filter_states",
    "dd_filter_distributor",
    "dd_dealer_idx",
)


def _clear_filters() -> None:
    """Reset cascading filters and the chosen dealer."""
    for key in _FILTER_KEYS:
        st.session_state.pop(key, None)


def _filter_options(rows: list[dict], key: str, predicates: list) -> list[str]:
    """Return sorted unique values of `key` for rows matching every predicate."""
    matching = rows
    for pred in predicates:
        matching = [r for r in matching if pred(r)]
    return sorted({r[key] for r in matching if r.get(key)})


def _render_filters(retailers: list[dict]) -> dict | None:
    """Cascading filter UI. Returns the selected dealer dict (or None)."""
    header_cols = st.columns([4, 1])
    with header_cols[0]:
        st.subheader("1. Find a dealer")
    with header_cols[1]:
        if st.button(
            "Clear selections",
            use_container_width=True,
            key="dd_clear_filters",
            help="Reset Zone / State / Distributor / Dealer filters",
        ):
            _clear_filters()
            st.rerun()

    # --- Zone ---
    zones = sorted({r["zone"] for r in retailers if r.get("zone")})
    selected_zones = st.multiselect("Zone", options=zones, key="dd_filter_zones")

    # --- State (depends on Zone) ---
    state_preds = []
    if selected_zones:
        state_preds.append(lambda r: r.get("zone") in selected_zones)
    available_states = _filter_options(retailers, "state_name", state_preds)

    prior_states = st.session_state.get("dd_filter_states", [])
    valid_states = [s for s in prior_states if s in available_states]
    if valid_states != prior_states:
        st.session_state["dd_filter_states"] = valid_states

    selected_states = st.multiselect(
        "State", options=available_states, key="dd_filter_states"
    )

    # --- Distributor (depends on Zone + State) ---
    dist_preds = []
    if selected_zones:
        dist_preds.append(lambda r: r.get("zone") in selected_zones)
    if selected_states:
        dist_preds.append(lambda r: r.get("state_name") in selected_states)
    available_distributors = _filter_options(retailers, "distributor_name", dist_preds)

    prior_dist = st.session_state.get("dd_filter_distributor", "All")
    if prior_dist != "All" and prior_dist not in available_distributors:
        st.session_state["dd_filter_distributor"] = "All"

    distributor = st.selectbox(
        "Distributor",
        options=["All"] + available_distributors,
        key="dd_filter_distributor",
    )

    # --- Dealer (depends on all of the above) ---
    dealer_preds = list(dist_preds)
    if distributor != "All":
        dealer_preds.append(lambda r: r.get("distributor_name") == distributor)

    matching_dealers = retailers
    for pred in dealer_preds:
        matching_dealers = [r for r in matching_dealers if pred(r)]
    matching_dealers = sorted(
        matching_dealers, key=lambda r: r.get("retailer_name") or ""
    )

    if not matching_dealers:
        st.info("No dealers match these filters. Try widening the selection.")
        return None

    sf_ids = [r["sf_id"] for r in matching_dealers]
    labels = [
        f"{r.get('retailer_name', '')} ({r['sf_id']})" for r in matching_dealers
    ]

    prior_dealer = st.session_state.get("dd_filter_dealer")
    if prior_dealer is not None and prior_dealer not in sf_ids:
        st.session_state["dd_filter_dealer"] = None

    selected_idx = st.selectbox(
        "Dealer Name",
        options=range(len(labels)),
        format_func=lambda i: labels[i],
        index=None,
        placeholder="Choose a dealer...",
        key="dd_dealer_idx",
    )

    if selected_idx is None:
        return None
    return matching_dealers[selected_idx]


def _render_form(dealer: dict, user_name: str) -> None:
    st.subheader(f"2. Delivery details for {dealer.get('retailer_name', '')}")
    st.caption(
        f"SF ID: {dealer['sf_id']} · {dealer.get('distributor_name') or '—'} · "
        f"{dealer.get('state_name') or '—'} · {dealer.get('zone') or '—'}"
    )

    existing = db.get_dealer_details(dealer["sf_id"]) or {}

    form_keys = {
        "name": f"dd_name_{dealer['sf_id']}",
        "phone": f"dd_phone_{dealer['sf_id']}",
        "email": f"dd_email_{dealer['sf_id']}",
        "addr": f"dd_addr_{dealer['sf_id']}",
        "loaded": f"dd_loaded_{dealer['sf_id']}",
    }

    if not st.session_state.get(form_keys["loaded"]):
        st.session_state[form_keys["name"]] = existing.get("contact_name", "")
        st.session_state[form_keys["phone"]] = existing.get("phone", "")
        st.session_state[form_keys["email"]] = existing.get("email", "") or ""
        st.session_state[form_keys["addr"]] = existing.get("delivery_address", "")
        st.session_state[form_keys["loaded"]] = True

    if existing:
        st.success("Existing details loaded — edit and save to update.")

    with st.form(f"dealer_details_form_{dealer['sf_id']}", clear_on_submit=False):
        contact_name = st.text_input(
            "Name of the person",
            max_chars=120,
            key=form_keys["name"],
        )
        phone = st.text_input(
            "Phone number",
            max_chars=20,
            placeholder="e.g. +91 98765 43210",
            key=form_keys["phone"],
        )
        email = st.text_input(
            "E-mail ID",
            max_chars=120,
            placeholder="optional",
            key=form_keys["email"],
        )
        delivery_address = st.text_area(
            "Delivery address",
            height=120,
            placeholder="Door no., street, locality, city, state, PIN code",
            key=form_keys["addr"],
        )

        btn_cols = st.columns(2)
        with btn_cols[0]:
            submitted = st.form_submit_button(
                "Save details", use_container_width=True, type="primary"
            )
        with btn_cols[1]:
            cleared = st.form_submit_button(
                "Clear", use_container_width=True,
                help="Empty all fields for this dealer",
            )

    if cleared:
        for k in ("name", "phone", "email", "addr"):
            st.session_state[form_keys[k]] = ""
        st.rerun()

    if not submitted:
        return

    contact_name = contact_name.strip()
    phone = phone.strip()
    email = email.strip()
    delivery_address = delivery_address.strip()

    errors: list[str] = []
    if not contact_name:
        errors.append("Name of the person is required.")
    if not phone:
        errors.append("Phone number is required.")
    elif not _PHONE_RE.match(phone):
        errors.append("Phone number looks invalid.")
    if email and not _EMAIL_RE.match(email):
        errors.append("E-mail ID looks invalid.")
    if not delivery_address:
        errors.append("Delivery address is required.")

    if errors:
        for e in errors:
            st.error(e)
        return

    try:
        db.upsert_dealer_details(
            retailer_sf_id=dealer["sf_id"],
            contact_name=contact_name,
            phone=phone,
            email=email or None,
            delivery_address=delivery_address,
            user_name=user_name,
        )
        st.success("Details saved.")
        st.rerun()
    except ValueError as e:
        st.error(str(e))


def _render_captured_summary(retailers: list[dict]) -> None:
    """Show a quick overview of how many dealers already have details captured."""
    captured = db.get_all_dealer_details()
    total = len(retailers)
    done = sum(1 for r in retailers if r["sf_id"] in captured)
    pending = total - done

    cols = st.columns(3)
    cols[0].metric("Total dealers", f"{total:,}")
    cols[1].metric("Details captured", f"{done:,}")
    cols[2].metric("Pending", f"{pending:,}")

    if not captured:
        return

    with st.expander("View captured dealer details", expanded=False):
        rows = []
        retailer_by_id = {r["sf_id"]: r for r in retailers}
        for sf_id, d in captured.items():
            r = retailer_by_id.get(sf_id, {})
            rows.append({
                "SF ID": sf_id,
                "Dealer": r.get("retailer_name", ""),
                "Zone": r.get("zone", ""),
                "State": r.get("state_name", ""),
                "Distributor": r.get("distributor_name", ""),
                "Contact": d.get("contact_name", ""),
                "Phone": d.get("phone", ""),
                "Email": d.get("email", "") or "",
                "Address": d.get("delivery_address", ""),
            })
        rows.sort(key=lambda x: x["Dealer"])
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_dealer_details() -> None:
    if not st.session_state.get("authenticated"):
        st.warning("Please log in to continue.")
        st.stop()

    with st.spinner("Loading dealers..."):
        retailers = db.get_retailers()

    if not retailers:
        st.warning("No dealers found.")
        st.stop()

    _render_captured_summary(retailers)
    st.divider()

    dealer = _render_filters(retailers)
    if dealer is None:
        return

    st.divider()
    _render_form(dealer, st.session_state.get("user_name", "Unknown"))
