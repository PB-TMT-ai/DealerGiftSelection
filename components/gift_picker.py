"""Gift picker component with live balance math and save logic."""

from __future__ import annotations

import streamlit as st

import db
from utils.constants import VOUCHER_MIN_POINTS, VOUCHER_POINTS_TO_INR


def render_gift_picker(
    retailer: dict,
    catalog: list[dict],
    existing_selections: list[dict],
    user_name: str,
) -> None:
    """
    Render the gift picker UI for a retailer.

    Shows live running balance above the catalog, then full-width gift cards,
    voucher input, and save button. Designed for mobile-first vertical scrolling.
    """
    sf_id = retailer["sf_id"]
    earned = int(retailer["earned_points"])

    st.divider()
    st.markdown(f"### Gift Selection for {retailer['retailer_name']}")
    st.caption(f"SF ID: {sf_id} · Slab: {retailer.get('eligible_slab', '—')}")

    physical_gifts = [g for g in catalog if not g.get("is_flexible")]
    voucher_gift = next((g for g in catalog if g.get("is_flexible")), None)

    existing_map: dict[int, dict] = {}
    for sel in existing_selections:
        existing_map[sel["gift_id"]] = {
            "quantity": sel.get("quantity", 1),
            "points_used": sel.get("points_used", 0),
        }

    # ---------- Live Balance (read from session_state so it stays above cards) ----------
    live_physical, live_voucher = _read_live_totals(
        sf_id, physical_gifts, voucher_gift, existing_map
    )
    live_total = live_physical + live_voucher
    live_remaining = earned - live_total

    bal_cols = st.columns(4)
    with bal_cols[0]:
        st.metric("Earned", f"{earned:,}")
    with bal_cols[1]:
        st.metric("Redeeming", f"{live_total:,}")
    with bal_cols[2]:
        st.metric("Remaining", f"{live_remaining:,}")
    with bal_cols[3]:
        utilization = (live_total / earned * 100) if earned > 0 else 0
        st.metric("Utilization", f"{utilization:.0f}%")

    if live_remaining < 0:
        st.error(f"Over budget by {abs(live_remaining):,} points! Remove some items to save.")

    st.divider()

    # ---------- Physical Gift Cards (1 per row for mobile) ----------
    st.markdown("#### Physical Gifts")

    physical_total = 0
    selections: list[dict] = []

    for gift in physical_gifts:
        gift_id = gift["id"]
        pts = gift["points_required"]
        inr = gift.get("gift_value_inr", 0)
        existing_qty = existing_map.get(gift_id, {}).get("quantity", 0)

        with st.container(border=True):
            st.markdown(f"**{gift['name']}**")
            st.caption(f"Slab {gift.get('slab', '—')} · {pts:,} pts · ₹{inr:,}")

            qty = st.number_input(
                "Qty",
                min_value=0,
                max_value=5,
                value=existing_qty,
                step=1,
                key=f"gift_qty_{sf_id}_{gift_id}",
            )

            if qty > 0:
                cost = pts * qty
                physical_total += cost
                selections.append({
                    "gift_id": gift_id,
                    "points_used": pts,
                    "quantity": qty,
                })
                if pts * qty > earned:
                    st.caption(f"⚠️ Need {pts * qty - earned:,} more points")

    # ---------- Amazon Voucher ----------
    st.markdown("#### Amazon Voucher")

    voucher_points = 0
    remaining_after_physical = earned - physical_total

    if voucher_gift:
        voucher_id = voucher_gift["id"]
        existing_voucher = existing_map.get(voucher_id, {})
        existing_voucher_pts = existing_voucher.get("points_used", 0)

        if remaining_after_physical < VOUCHER_MIN_POINTS:
            st.warning(
                f"Unavailable — need {VOUCHER_MIN_POINTS}+ points remaining. "
                f"Current remaining: {remaining_after_physical:,} points."
            )
        else:
            default_voucher = existing_voucher_pts if existing_voucher_pts >= VOUCHER_MIN_POINTS else remaining_after_physical
            default_voucher = max(VOUCHER_MIN_POINTS, min(default_voucher, remaining_after_physical))

            voucher_points = st.number_input(
                "Voucher amount (in points)",
                min_value=0,
                max_value=remaining_after_physical,
                value=default_voucher if existing_voucher_pts > 0 else 0,
                step=50,
                key=f"voucher_pts_{sf_id}",
                help=f"Minimum: {VOUCHER_MIN_POINTS} points. 1 point = ₹{VOUCHER_POINTS_TO_INR}",
            )

            if voucher_points > 0:
                inr_value = voucher_points * VOUCHER_POINTS_TO_INR
                st.caption(f"Voucher will be issued for **₹{inr_value:,}**")

                if voucher_points < VOUCHER_MIN_POINTS:
                    st.error(f"Minimum voucher amount is {VOUCHER_MIN_POINTS} points.")
                    voucher_points = 0
                else:
                    selections.append({
                        "gift_id": voucher_id,
                        "points_used": voucher_points,
                        "quantity": 1,
                    })

    st.divider()

    # ---------- Save / Clear ----------
    total_used = physical_total + voucher_points
    remaining = earned - total_used

    can_save = (
        len(selections) > 0
        and remaining >= 0
        and all(
            s["points_used"] >= VOUCHER_MIN_POINTS
            for s in selections
            if voucher_gift and s["gift_id"] == voucher_gift["id"]
        )
    )

    btn_cols = st.columns(2)
    with btn_cols[0]:
        if st.button(
            "Save Selections",
            disabled=not can_save,
            use_container_width=True,
            type="primary",
            key=f"save_{sf_id}",
        ):
            _save_selections(sf_id, selections, user_name, existing_selections)

    with btn_cols[1]:
        if st.button(
            "Clear All",
            use_container_width=True,
            key=f"clear_{sf_id}",
        ):
            _clear_selections(sf_id, user_name)

    if not can_save and len(selections) == 0:
        st.caption("Select at least one gift to save.")


def _read_live_totals(
    sf_id: str,
    physical_gifts: list[dict],
    voucher_gift: dict | None,
    existing_map: dict[int, dict],
) -> tuple[int, int]:
    """Read current widget state to show live balance above the cards."""
    physical_total = 0
    for gift in physical_gifts:
        key = f"gift_qty_{sf_id}_{gift['id']}"
        default_qty = existing_map.get(gift["id"], {}).get("quantity", 0)
        qty = st.session_state.get(key, default_qty)
        physical_total += gift["points_required"] * qty

    voucher_pts = 0
    if voucher_gift:
        key = f"voucher_pts_{sf_id}"
        if key in st.session_state:
            voucher_pts = st.session_state[key]
        else:
            existing_pts = existing_map.get(voucher_gift["id"], {}).get("points_used", 0)
            if existing_pts > 0:
                voucher_pts = existing_pts

    return physical_total, voucher_pts


def _save_selections(
    sf_id: str,
    selections: list[dict],
    user_name: str,
    existing_selections: list[dict],
) -> None:
    """Execute the save via RPC with confirmation."""
    if existing_selections:
        st.info("This will **replace** the existing selections with the new set.")

    try:
        with st.spinner("Saving selections..."):
            db.replace_selections(sf_id, selections, user_name)
        st.toast("Selections saved successfully!", icon="✅")
        st.rerun()
    except Exception as e:
        error_msg = str(e)
        if "exceed" in error_msg.lower():
            st.error(f"Save rejected: total points exceed earned points. {error_msg}")
        elif "minimum" in error_msg.lower() or "voucher" in error_msg.lower():
            st.error(f"Save rejected: voucher below minimum. {error_msg}")
        else:
            st.error(f"Failed to save selections: {error_msg}")


def _clear_selections(sf_id: str, user_name: str) -> None:
    try:
        with st.spinner("Clearing selections..."):
            db.replace_selections(sf_id, [], user_name)
        st.toast("Selections cleared.", icon="🗑️")
        st.rerun()
    except Exception as e:
        st.error(f"Failed to clear: {e}")
