"""Gift Selection view — filters-first dealer picker, modal gift picker."""

from __future__ import annotations

import streamlit as st

import db
from components.gift_picker import open_gift_picker_dialog
from components.retailer_table import (
    apply_filters,
    render_filters,
    render_retailer_table,
)


def render_gift_selection() -> None:
    if not st.session_state.get("authenticated"):
        st.warning("Please log in to continue.")
        st.stop()

    with st.spinner("Loading data..."):
        retailers = db.get_retailers()
        all_selections = db.get_all_selections()
        catalog = db.get_gifts_catalog()

    points_used_map: dict[str, int] = {}
    for sel in all_selections:
        sf_id = sel["retailer_sf_id"]
        pts = sel["points_used"] * sel.get("quantity", 1)
        points_used_map[sf_id] = points_used_map.get(sf_id, 0) + pts

    if not retailers:
        st.warning("No retailers found. Have you run the seeding script?")
        st.stop()

    filters = render_filters(retailers)
    filtered = apply_filters(retailers, points_used_map, filters)

    selected_sf_id = render_retailer_table(filtered, all_selections=all_selections)

    if selected_sf_id:
        retailer = db.get_retailer(selected_sf_id)
        if retailer:
            existing_selections = [
                s for s in all_selections if s["retailer_sf_id"] == selected_sf_id
            ]
            open_gift_picker_dialog(
                retailer=retailer,
                catalog=catalog,
                existing_selections=existing_selections,
                user_name=st.session_state.get("user_name", "Unknown"),
            )
        else:
            st.error(f"Retailer {selected_sf_id} not found.")
