"""Combo suggestions panel component."""

from __future__ import annotations

import streamlit as st

from utils.constants import VOUCHER_MIN_POINTS
from utils.points import suggest_combinations


def render_suggestions(balance: int, catalog: list[dict]) -> None:
    """
    Display 2-3 suggested gift combos that best utilize the available balance.
    """
    if balance <= 0:
        st.caption("No points available for redemption.")
        return

    combos = suggest_combinations(balance, catalog, max_suggestions=3)

    if not combos:
        if balance < VOUCHER_MIN_POINTS:
            st.info(
                f"Insufficient points for any redemption. "
                f"Minimum for Amazon Voucher is {VOUCHER_MIN_POINTS} points; "
                f"current balance is {balance:,} points."
            )
        else:
            st.info("No valid combinations found for the current balance.")
        return

    st.markdown(f"**Top suggestions** for {balance:,} available points:")

    for i, combo in enumerate(combos):
        with st.container(border=True):
            # Header
            utilization_pct = combo.utilization * 100
            st.markdown(f"**Option {i + 1}** — {utilization_pct:.0f}% utilization")

            # Items
            parts = []
            for item in combo.items:
                if item.is_voucher:
                    parts.append(f"Amazon Voucher: {item.points_required:,} pts")
                else:
                    parts.append(
                        f"{item.quantity}× {item.gift_name}: "
                        f"{item.points_required * item.quantity:,} pts"
                    )

            for part in parts:
                st.caption(f"  • {part}")

            # Totals
            cols = st.columns(2)
            with cols[0]:
                st.caption(f"Points: {combo.total_points:,}")
            with cols[1]:
                unused = balance - combo.total_points
                if unused > 0:
                    st.caption(f"Unused: {unused:,} pts")
                else:
                    st.caption("Fully utilized")
