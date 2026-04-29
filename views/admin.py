"""Admin dashboard view — KPIs, summary tables, Excel export. Mobile-friendly."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

import db
from utils.constants import VOUCHER_POINTS_TO_INR
from utils.excel_export import (
    build_consolidated_rows,
    build_dealer_details_rows,
    build_gift_summary,
    build_state_summary,
    build_zone_summary,
    generate_export,
)


def render_admin() -> None:
    if not st.session_state.get("authenticated"):
        st.warning("Please log in to continue.")
        st.stop()

    if st.session_state.get("role") != "admin":
        st.error("Admin access required.")
        st.stop()

    with st.spinner("Loading consolidated data..."):
        retailers = db.get_all_retailers_with_selections()
        retailers = [r for r in retailers if int(r.get("earned_points") or 0) > 0]

    if not retailers:
        st.warning("No retailer data found. Have you run the seeding script?")
        st.stop()

    total_retailers = len(retailers)
    total_earned = sum(int(r["earned_points"]) for r in retailers)
    total_used = sum(r.get("points_used", 0) for r in retailers)
    utilization_pct = (total_used / total_earned * 100) if total_earned > 0 else 0
    with_selections = sum(1 for r in retailers if r.get("points_used", 0) > 0)

    estimated_total_cost = 0
    for r in retailers:
        for sel in r.get("selections", []):
            gift_info = sel.get("gifts_catalog", {})
            if not gift_info:
                continue
            qty = sel.get("quantity", 1)
            pts = sel.get("points_used", 0)
            if gift_info.get("is_flexible"):
                estimated_total_cost += pts * VOUCHER_POINTS_TO_INR
            else:
                estimated_total_cost += (gift_info.get("gift_value_inr", 0) or 0) * qty

    # KPIs laid out as 2x2 so they stay readable on mobile
    row1 = st.columns(2)
    with row1[0]:
        st.metric("Total Dealers", f"{total_retailers:,}")
    with row1[1]:
        st.metric("With Selections", f"{with_selections:,}")

    row2 = st.columns(2)
    with row2[0]:
        st.metric("Utilization", f"{utilization_pct:.1f}%")
    with row2[1]:
        st.metric("Estimated Total Cost", f"₹{estimated_total_cost:,}")

    st.divider()

    consolidated_rows = build_consolidated_rows(retailers)
    df_consolidated = pd.DataFrame(consolidated_rows)
    zone_df = build_zone_summary(retailers)
    state_df = build_state_summary(retailers)
    gift_df = build_gift_summary(retailers)

    try:
        dealer_details_map = db.get_all_dealer_details()
    except db.DealerDetailsTableMissing:
        dealer_details_map = {}
        st.warning(
            "Dealer Details table is not yet set up — the export's Dealer "
            "Details sheet will list all dealers with blank contact fields."
        )
    dealer_details_df = build_dealer_details_rows(retailers, dealer_details_map)

    with st.expander("Consolidated Retailer Data", expanded=True):
        st.dataframe(df_consolidated, use_container_width=True, hide_index=True)

    with st.expander("Zone-Wise Summary", expanded=False):
        if not zone_df.empty:
            st.dataframe(zone_df, use_container_width=True, hide_index=True)
        else:
            st.caption("No zone data available.")

    with st.expander("State-Wise Summary", expanded=False):
        if not state_df.empty:
            st.dataframe(state_df, use_container_width=True, hide_index=True)
        else:
            st.caption("No state data available.")

    with st.expander("Gift-Wise Summary", expanded=False):
        if not gift_df.empty:
            st.dataframe(gift_df, use_container_width=True, hide_index=True)
        else:
            st.caption("No gift selection data yet.")

    with st.expander("Dealer Delivery Details", expanded=False):
        if not dealer_details_df.empty:
            st.dataframe(
                dealer_details_df, use_container_width=True, hide_index=True
            )
        else:
            st.caption("No dealer delivery details captured yet.")

    st.divider()
    st.markdown("### Export")

    today = datetime.now().strftime("%Y%m%d")
    filename = f"Q4_Consolidated_{today}.xlsx"

    try:
        excel_bytes = generate_export(
            consolidated=consolidated_rows,
            zone_summary=zone_df,
            state_summary=state_df,
            gift_summary=gift_df,
            dealer_details=dealer_details_df,
        )
        st.download_button(
            label=f"Download {filename}",
            data=excel_bytes,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"Failed to generate export: {e}")
