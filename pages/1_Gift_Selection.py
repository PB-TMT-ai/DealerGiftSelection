"""
Gift Selection Page — SM/TM View

Accessible to both sm_tm and admin roles.
Allows filtering retailers, viewing their point balances,
and managing gift selections via the gift picker.
"""

from __future__ import annotations

import streamlit as st

# Auth guard
if not st.session_state.get("authenticated"):
    st.warning("Please log in from the main page.")
    st.stop()

import db  # noqa: E402
from components.gift_picker import render_gift_picker  # noqa: E402
from components.retailer_table import (  # noqa: E402
    apply_filters,
    render_filters,
    render_retailer_table,
)
from components.suggestions import render_suggestions  # noqa: E402

st.markdown("## Gift Selection")

# Load data (single batch — avoids N+1 queries)
with st.spinner("Loading data..."):
    retailers = db.get_retailers()
    all_selections = db.get_all_selections()
    catalog = db.get_gifts_catalog()

# Compute points used per retailer from the prefetched selections
points_used_map: dict[str, int] = {}
for sel in all_selections:
    sf_id = sel["retailer_sf_id"]
    pts = sel["points_used"] * sel.get("quantity", 1)
    points_used_map[sf_id] = points_used_map.get(sf_id, 0) + pts

if not retailers:
    st.warning("No retailers found. Have you run the seeding script?")
    st.stop()

# Filters
filters = render_filters(retailers)

# Apply filters
filtered = apply_filters(retailers, points_used_map, filters)

# Retailer table + selection (pass all_selections to avoid per-row DB calls)
selected_sf_id = render_retailer_table(filtered, all_selections=all_selections)

# Gift picker for selected retailer
if selected_sf_id:
    retailer = db.get_retailer(selected_sf_id)
    if retailer:
        existing_selections = [s for s in all_selections if s["retailer_sf_id"] == selected_sf_id]

        # Suggestions panel
        used = points_used_map.get(selected_sf_id, 0)
        balance = int(retailer["earned_points"]) - used

        with st.expander("Combo Suggestions", expanded=False):
            render_suggestions(balance, catalog)

        # Gift picker
        render_gift_picker(
            retailer=retailer,
            catalog=catalog,
            existing_selections=existing_selections,
            user_name=st.session_state.get("user_name", "Unknown"),
        )
    else:
        st.error(f"Retailer {selected_sf_id} not found.")
