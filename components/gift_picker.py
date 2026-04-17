"""Gift picker component — modal dialog with sticky balance and hard-block rules."""

from __future__ import annotations

import streamlit as st

import db
from components.suggestions import render_suggestions
from utils.constants import VOUCHER_MIN_POINTS, VOUCHER_POINTS_TO_INR


@st.dialog("Gift Selection", width="large")
def open_gift_picker_dialog(
    retailer: dict,
    catalog: list[dict],
    existing_selections: list[dict],
    user_name: str,
) -> None:
    """Modal gift picker for a retailer."""
    _render_gift_picker_body(retailer, catalog, existing_selections, user_name)


def _render_gift_picker_body(
    retailer: dict,
    catalog: list[dict],
    existing_selections: list[dict],
    user_name: str,
) -> None:
    sf_id = retailer["sf_id"]
    earned = int(retailer["earned_points"])

    st.markdown(f"### {retailer['retailer_name']}")
    st.caption(f"SF ID: {sf_id} · Slab: {retailer.get('eligible_slab', '—')}")

    physical_gifts = [g for g in catalog if not g.get("is_flexible")]
    voucher_gift = next((g for g in catalog if g.get("is_flexible")), None)

    existing_map: dict[int, dict] = {}
    for sel in existing_selections:
        existing_map[sel["gift_id"]] = {
            "quantity": sel.get("quantity", 1),
            "points_used": sel.get("points_used", 0),
        }

    live_physical, live_voucher_raw = _read_live_totals(
        sf_id, physical_gifts, voucher_gift, existing_map
    )
    # Cap the displayed voucher against what the voucher branch will actually
    # accept — keeps the sticky balance honest when session state is stale
    # (e.g. after a physical gift was just added that ate into the voucher room).
    remaining_for_voucher = earned - live_physical
    if voucher_gift is None or remaining_for_voucher < VOUCHER_MIN_POINTS:
        live_voucher = 0
    else:
        live_voucher = min(live_voucher_raw, remaining_for_voucher)
    live_total = live_physical + live_voucher
    live_remaining = earned - live_total

    # Sticky balance bar — single HTML block so CSS sticky actually works.
    # Streamlit renders each st.metric as a separate DOM element, which breaks
    # CSS sticky wrapping. A single st.markdown block stays as one element.
    utilization = (live_total / earned * 100) if earned > 0 else 0
    remaining_color = "#ff4b4b" if live_remaining < 0 else "#31c48d"

    st.markdown(
        f"""
        <style>
        .sticky-balance {{
            position: sticky;
            top: 0;
            z-index: 999;
            background: var(--background-color, #ffffff);
            padding: 0.75rem 0.25rem;
            border-bottom: 2px solid rgba(128, 128, 128, 0.15);
            margin-bottom: 0.75rem;
            display: flex;
            justify-content: space-between;
            gap: 0.25rem;
        }}
        .sticky-balance .bal-metric {{
            flex: 1;
            text-align: center;
        }}
        .sticky-balance .bal-label {{
            display: block;
            font-size: 0.7rem;
            color: #808080;
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }}
        .sticky-balance .bal-value {{
            display: block;
            font-size: 1.2rem;
            font-weight: 700;
        }}
        </style>
        <div class="sticky-balance">
            <div class="bal-metric">
                <span class="bal-label">Earned</span>
                <span class="bal-value">{earned:,}</span>
            </div>
            <div class="bal-metric">
                <span class="bal-label">Redeeming</span>
                <span class="bal-value">{live_total:,}</span>
            </div>
            <div class="bal-metric">
                <span class="bal-label">Remaining</span>
                <span class="bal-value" style="color:{remaining_color}">{live_remaining:,}</span>
            </div>
            <div class="bal-metric">
                <span class="bal-label">Utilization</span>
                <span class="bal-value">{utilization:.0f}%</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if live_remaining < 0:
        st.error(f"Over budget by {abs(live_remaining):,} points! Remove some items to save.")

    # Suggestions only surface when the user is within budget, and always
    # priced against what is left — they can never push a user over earned.
    if live_remaining >= 0 and voucher_gift is not None:
        with st.expander("💡 Suggested combos within your balance", expanded=False):
            render_suggestions(live_remaining, catalog)

    st.divider()

    # ---------- Physical Gift Cards ----------
    st.markdown("#### Physical Gifts")

    physical_total = 0
    selections: list[dict] = []

    for gift in physical_gifts:
        gift_id = gift["id"]
        pts = gift["points_required"]
        inr = gift.get("gift_value_inr", 0)
        existing_qty = existing_map.get(gift_id, {}).get("quantity", 0)

        # Hard-block: cap this gift's qty at what the remaining budget allows,
        # while never forcing the user below a value they already loaded.
        current_qty = st.session_state.get(
            f"gift_qty_{sf_id}_{gift_id}", existing_qty
        )
        remaining_excluding_self = earned - (live_total - pts * current_qty)
        affordable_qty = remaining_excluding_self // pts if pts > 0 else 0
        max_qty = max(current_qty, int(affordable_qty))
        max_value = max_qty

        with st.container(border=True):
            st.markdown(f"**{gift['name']}**")
            st.caption(f"Slab {gift.get('slab', '—')} · {pts:,} pts · ₹{inr:,}")

            if max_value == 0 and current_qty == 0:
                st.error(f"Not enough points remaining to add this gift ({pts:,} pts required).")
                qty = 0
                st.session_state[f"gift_qty_{sf_id}_{gift_id}"] = 0
            else:
                qty = st.number_input(
                    "Qty",
                    min_value=0,
                    max_value=max_value,
                    value=min(existing_qty, max_value),
                    step=1,
                    key=f"gift_qty_{sf_id}_{gift_id}",
                )

            if qty > 0:
                physical_total += pts * qty
                selections.append({
                    "gift_id": gift_id,
                    "points_used": pts,
                    "quantity": qty,
                })

    # ---------- Amazon Voucher ----------
    st.markdown("#### Amazon Voucher")

    voucher_points = 0
    remaining_after_physical = earned - physical_total

    if voucher_gift:
        voucher_id = voucher_gift["id"]
        existing_voucher = existing_map.get(voucher_id, {})
        existing_voucher_pts = existing_voucher.get("points_used", 0)

        if remaining_after_physical < VOUCHER_MIN_POINTS:
            st.error(
                f"Amazon Voucher unavailable — {remaining_after_physical:,} points "
                f"remaining is below the {VOUCHER_MIN_POINTS}-point minimum. "
                "Remove a physical gift to enable the voucher."
            )
            # Zero out any stale voucher value so it does not silently save.
            st.session_state[f"voucher_pts_{sf_id}"] = 0
        else:
            default_voucher = (
                existing_voucher_pts
                if existing_voucher_pts >= VOUCHER_MIN_POINTS
                else remaining_after_physical
            )
            default_voucher = max(
                VOUCHER_MIN_POINTS, min(default_voucher, remaining_after_physical)
            )

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
                    st.error(
                        f"Voucher amount must be at least {VOUCHER_MIN_POINTS} points."
                    )
                    voucher_points = 0
                else:
                    selections.append({
                        "gift_id": voucher_id,
                        "points_used": voucher_points,
                        "quantity": 1,
                    })

    st.divider()

    # ---------- Save / Clear / Close ----------
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

    btn_cols = st.columns(3)
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

    with btn_cols[2]:
        if st.button(
            "Close",
            use_container_width=True,
            key=f"close_{sf_id}",
        ):
            st.session_state.pop("retailer_selector", None)
            st.rerun()

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
        st.session_state.pop("retailer_selector", None)
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
        st.session_state.pop("retailer_selector", None)
        st.rerun()
    except Exception as e:
        st.error(f"Failed to clear: {e}")
