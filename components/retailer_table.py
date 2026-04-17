"""Filterable retailer table component."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.constants import VOUCHER_POINTS_TO_INR


def render_filters(retailers: list[dict]) -> dict:
    """
    Render cascading filter controls in the sidebar.

    Selection in an upstream filter narrows the options shown in
    downstream filters: Zone -> State -> Distributor.
    """
    with st.sidebar:
        st.markdown("### Filters")

        zones = sorted({r["zone"] for r in retailers if r.get("zone")})

        selected_zones = st.multiselect("Zone", options=zones, key="filter_zones")

        # States cascade from selected zones
        if selected_zones:
            available_states = sorted({
                r["state_name"] for r in retailers
                if r.get("state_name") and r.get("zone") in selected_zones
            })
        else:
            available_states = sorted({
                r["state_name"] for r in retailers if r.get("state_name")
            })

        # Drop any previously-selected states that are no longer valid
        prior_states = st.session_state.get("filter_states", [])
        valid_states = [s for s in prior_states if s in available_states]
        if valid_states != prior_states:
            st.session_state["filter_states"] = valid_states

        selected_states = st.multiselect(
            "State", options=available_states, key="filter_states"
        )

        # Distributors cascade from selected zones AND states
        matching = retailers
        if selected_zones:
            matching = [r for r in matching if r.get("zone") in selected_zones]
        if selected_states:
            matching = [r for r in matching if r.get("state_name") in selected_states]
        available_distributors = sorted({
            r["distributor_name"] for r in matching if r.get("distributor_name")
        })

        # Reset distributor selection if no longer valid
        prior_dist = st.session_state.get("filter_distributor", "All")
        if prior_dist != "All" and prior_dist not in available_distributors:
            st.session_state["filter_distributor"] = "All"

        distributor = st.selectbox(
            "Distributor",
            options=["All"] + available_distributors,
            key="filter_distributor",
        )

        retailer_search = st.text_input(
            "Search retailer name",
            placeholder="Type to filter...",
            key="filter_retailer_search",
        )

        has_selections = st.radio(
            "Has selections?",
            options=["All", "Yes", "No"],
            index=0,
            horizontal=True,
            key="filter_has_selections",
        )

    return {
        "distributor": distributor if distributor != "All" else None,
        "states": selected_states or None,
        "zones": selected_zones or None,
        "retailer_search": retailer_search.strip() or None,
        "has_selections": {"All": None, "Yes": True, "No": False}[has_selections],
    }


def apply_filters(
    retailers: list[dict],
    points_used_map: dict[str, int],
    filters: dict,
) -> list[dict]:
    """Apply filter criteria to the retailer list and return matching rows."""
    result = []

    for r in retailers:
        sf_id = r["sf_id"]
        used = points_used_map.get(sf_id, 0)
        earned = int(r["earned_points"])
        balance = earned - used

        if filters["distributor"] and r.get("distributor_name") != filters["distributor"]:
            continue
        if filters["states"] and r.get("state_name") not in filters["states"]:
            continue
        if filters["zones"] and r.get("zone") not in filters["zones"]:
            continue
        if filters["retailer_search"]:
            if filters["retailer_search"].lower() not in r.get("retailer_name", "").lower():
                continue

        has_sel = used > 0
        if filters["has_selections"] is True and not has_sel:
            continue
        if filters["has_selections"] is False and has_sel:
            continue

        result.append({
            **r,
            "points_used": used,
            "balance": balance,
        })

    return result


def render_retailer_table(
    filtered_retailers: list[dict],
    all_selections: list[dict] | None = None,
) -> str | None:
    """
    Render the retailer table and return the sf_id of the selected retailer (if any).

    ``all_selections`` is the full list of gift_selection rows (with gifts_catalog joined).
    If provided, selection summaries are built without extra DB queries.
    """
    if not filtered_retailers:
        st.info("No retailers match these filters. Try widening the selection.")
        return None

    # Pre-group selections by retailer if provided
    sel_by_retailer: dict[str, list[dict]] = {}
    if all_selections:
        for sel in all_selections:
            sf_id = sel["retailer_sf_id"]
            sel_by_retailer.setdefault(sf_id, []).append(sel)

    display_data = []
    for r in filtered_retailers:
        used = r.get("points_used", 0)
        earned = int(r["earned_points"])
        balance = earned - used

        # Build selection summary from pre-fetched data
        selections = sel_by_retailer.get(r["sf_id"], [])
        summary_parts = []
        for sel in selections:
            gift_info = sel.get("gifts_catalog", {})
            if not gift_info:
                continue
            gift_name = gift_info.get("name", "Unknown")
            qty = sel.get("quantity", 1)
            pts = sel.get("points_used", 0)
            if gift_info.get("is_flexible"):
                inr_val = pts * VOUCHER_POINTS_TO_INR
                summary_parts.append(f"Voucher (₹{inr_val:,})")
            else:
                summary_parts.append(f"{qty}× {gift_name}")

        display_data.append({
            "SF ID": r["sf_id"],
            "Retailer Name": r.get("retailer_name", ""),
            "Distributor": r.get("distributor_name", ""),
            "State": r.get("state_name", ""),
            "Zone": r.get("zone", ""),
            "Earned Points": earned,
            "Points Used": used,
            "Balance": balance,
            "Current Selections": ", ".join(summary_parts) if summary_parts else "—",
        })

    df = pd.DataFrame(display_data)

    st.markdown(f"**{len(df)} retailers** matching filters")

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Balance": st.column_config.NumberColumn(
                "Balance",
                help="Earned points minus points used",
            ),
        },
    )

    # Retailer selector
    sf_ids = [r["sf_id"] for r in filtered_retailers]
    names = [f"{r['retailer_name']} ({r['sf_id']})" for r in filtered_retailers]

    selected_idx = st.selectbox(
        "Select a retailer to manage gifts",
        options=range(len(names)),
        format_func=lambda i: names[i],
        index=None,
        placeholder="Choose a retailer...",
        key="retailer_selector",
    )

    if selected_idx is not None:
        return sf_ids[selected_idx]

    return None
