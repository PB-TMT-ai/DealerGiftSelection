"""
Consolidated Admin View

Accessible only to admin role. Shows KPIs, consolidated retailer table,
zone/state/gift summaries, and Excel export.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

# Auth guard
if not st.session_state.get("authenticated"):
    st.warning("Please log in from the main page.")
    st.stop()

if st.session_state.get("role") != "admin":
    st.error("Admin access required.")
    st.stop()

import db  # noqa: E402
from utils.constants import VOUCHER_POINTS_TO_INR  # noqa: E402
from utils.excel_export import (  # noqa: E402
    build_consolidated_rows,
    build_gift_summary,
    build_state_summary,
    build_zone_summary,
    generate_export,
)

st.markdown("## Consolidated Admin Dashboard")

# Load all data
with st.spinner("Loading consolidated data..."):
    retailers = db.get_all_retailers_with_selections()

if not retailers:
    st.warning("No retailer data found. Have you run the seeding script?")
    st.stop()

# ---------------------------------------------------------------------------
# KPI Row
# ---------------------------------------------------------------------------
total_retailers = len(retailers)
total_earned = sum(int(r["earned_points"]) for r in retailers)
total_used = sum(r.get("points_used", 0) for r in retailers)
utilization_pct = (total_used / total_earned * 100) if total_earned > 0 else 0
with_selections = sum(1 for r in retailers if r.get("points_used", 0) > 0)
without_selections = total_retailers - with_selections

# Compute estimated total cost across all selections
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

kpi_cols = st.columns(4)
with kpi_cols[0]:
    st.metric("Total Dealers", f"{total_retailers:,}")
with kpi_cols[1]:
    st.metric("With Selections", f"{with_selections:,}")
with kpi_cols[2]:
    st.metric("Utilization", f"{utilization_pct:.1f}%")
with kpi_cols[3]:
    st.metric("Estimated Total Cost", f"₹{estimated_total_cost:,}")

st.divider()

# ---------------------------------------------------------------------------
# Consolidated Table
# ---------------------------------------------------------------------------
st.markdown("### Consolidated Retailer Data")

consolidated_rows = build_consolidated_rows(retailers)
df_consolidated = pd.DataFrame(consolidated_rows)

st.dataframe(df_consolidated, use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------------------------
# Zone Summary
# ---------------------------------------------------------------------------
st.markdown("### Zone-Wise Summary")
zone_df = build_zone_summary(retailers)
if not zone_df.empty:
    st.dataframe(zone_df, use_container_width=True, hide_index=True)
else:
    st.caption("No zone data available.")

st.divider()

# ---------------------------------------------------------------------------
# State Summary
# ---------------------------------------------------------------------------
st.markdown("### State-Wise Summary")
state_df = build_state_summary(retailers)
if not state_df.empty:
    st.dataframe(state_df, use_container_width=True, hide_index=True)
else:
    st.caption("No state data available.")

st.divider()

# ---------------------------------------------------------------------------
# Gift Summary
# ---------------------------------------------------------------------------
st.markdown("### Gift-Wise Summary")
gift_df = build_gift_summary(retailers)
if not gift_df.empty:
    st.dataframe(gift_df, use_container_width=True, hide_index=True)
else:
    st.caption("No gift selection data yet.")

st.divider()

# ---------------------------------------------------------------------------
# Excel Export
# ---------------------------------------------------------------------------
st.markdown("### Export")

today = datetime.now().strftime("%Y%m%d")
filename = f"Q4_Consolidated_{today}.xlsx"

try:
    excel_bytes = generate_export(
        consolidated=consolidated_rows,
        zone_summary=zone_df,
        state_summary=state_df,
        gift_summary=gift_df,
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
