"""Excel export utility for the Admin consolidated view."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pandas as pd
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from utils.constants import VOUCHER_POINTS_TO_INR


def generate_export(
    consolidated: list[dict],
    zone_summary: pd.DataFrame,
    state_summary: pd.DataFrame,
    gift_summary: pd.DataFrame,
) -> bytes:
    """
    Generate a styled Excel workbook with 4 sheets:
      1. Consolidated — one row per retailer with gift details
      2. Zone Summary
      3. State Summary
      4. Gift Summary

    Returns the workbook as bytes for st.download_button.
    """
    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        # Sheet 1: Consolidated
        df_consolidated = pd.DataFrame(consolidated)
        df_consolidated.to_excel(writer, sheet_name="Consolidated", index=False)

        # Sheet 2: Zone Summary
        zone_summary.to_excel(writer, sheet_name="Zone Summary", index=False)

        # Sheet 3: State Summary
        state_summary.to_excel(writer, sheet_name="State Summary", index=False)

        # Sheet 4: Gift Summary
        gift_summary.to_excel(writer, sheet_name="Gift Summary", index=False)

        # Style all sheets: bold header, frozen first row, auto-width
        wb = writer.book
        bold_font = Font(bold=True)

        for ws in wb.worksheets:
            # Bold header row
            for cell in ws[1]:
                cell.font = bold_font

            # Freeze first row
            ws.freeze_panes = "A2"

            # Auto-width columns (approximate)
            for col_idx in range(1, ws.max_column + 1):
                max_len = 0
                col_letter = get_column_letter(col_idx)
                for row in ws.iter_rows(
                    min_col=col_idx, max_col=col_idx, values_only=True
                ):
                    cell_val = str(row[0]) if row[0] is not None else ""
                    max_len = max(max_len, len(cell_val))
                ws.column_dimensions[col_letter].width = min(max_len + 4, 50)

    return buffer.getvalue()


def build_consolidated_rows(retailers: list[dict]) -> list[dict]:
    """
    Transform retailer data with selections into flat rows for the consolidated sheet.
    """
    rows = []
    for r in retailers:
        earned = int(r["earned_points"])
        used = r.get("points_used", 0)
        balance = earned - used
        selections = r.get("selections", [])

        # Build gifts summary string
        gift_parts = []
        total_value_inr = 0
        for sel in selections:
            gift_info = sel.get("gifts_catalog", {})
            if not gift_info:
                continue
            qty = sel.get("quantity", 1)
            pts = sel.get("points_used", 0)

            if gift_info.get("is_flexible"):
                inr = pts * VOUCHER_POINTS_TO_INR
                gift_parts.append(f"Voucher (₹{inr:,})")
                total_value_inr += inr
            else:
                gift_name = gift_info.get("name", "Unknown")
                gift_inr = gift_info.get("gift_value_inr", 0) or 0
                gift_parts.append(f"{qty}× {gift_name}")
                total_value_inr += gift_inr * qty

        rows.append({
            "SF ID": r["sf_id"],
            "Retailer Name": r.get("retailer_name", ""),
            "Distributor": r.get("distributor_name", ""),
            "State": r.get("state_name", ""),
            "District": r.get("district_name", ""),
            "Zone": r.get("zone", ""),
            "Slab": r.get("eligible_slab", ""),
            "Earned Points": earned,
            "Points Used": used,
            "Balance": balance,
            "Utilization %": round(used / earned * 100, 1) if earned > 0 else 0,
            "Gift Selections": ", ".join(gift_parts) if gift_parts else "—",
            "Total Value (₹)": total_value_inr,
        })

    return rows


def build_zone_summary(retailers: list[dict]) -> pd.DataFrame:
    """Aggregate by zone."""
    zone_data: dict[str, dict] = {}

    for r in retailers:
        zone = r.get("zone") or "Unknown"
        if zone not in zone_data:
            zone_data[zone] = {
                "Zone": zone,
                "Total Retailers": 0,
                "Retailers With Selections": 0,
                "Total Earned Points": 0,
                "Total Points Used": 0,
                "Total Value (₹)": 0,
            }

        z = zone_data[zone]
        z["Total Retailers"] += 1
        z["Total Earned Points"] += int(r["earned_points"])
        z["Total Points Used"] += r.get("points_used", 0)

        if r.get("points_used", 0) > 0:
            z["Retailers With Selections"] += 1

        for sel in r.get("selections", []):
            gift_info = sel.get("gifts_catalog", {})
            if not gift_info:
                continue
            pts = sel.get("points_used", 0)
            qty = sel.get("quantity", 1)
            if gift_info.get("is_flexible"):
                z["Total Value (₹)"] += pts * VOUCHER_POINTS_TO_INR
            else:
                z["Total Value (₹)"] += (gift_info.get("gift_value_inr", 0) or 0) * qty

    df = pd.DataFrame(list(zone_data.values()))
    if not df.empty:
        df["Utilization %"] = (df["Total Points Used"] / df["Total Earned Points"] * 100).round(1)
    return df


def build_state_summary(retailers: list[dict]) -> pd.DataFrame:
    """Aggregate by state."""
    state_data: dict[str, dict] = {}

    for r in retailers:
        state = r.get("state_name") or "Unknown"
        if state not in state_data:
            state_data[state] = {
                "State": state,
                "Total Retailers": 0,
                "Retailers With Selections": 0,
                "Total Earned Points": 0,
                "Total Points Used": 0,
            }

        s = state_data[state]
        s["Total Retailers"] += 1
        s["Total Earned Points"] += int(r["earned_points"])
        s["Total Points Used"] += r.get("points_used", 0)

        if r.get("points_used", 0) > 0:
            s["Retailers With Selections"] += 1

    df = pd.DataFrame(list(state_data.values()))
    if not df.empty:
        df["Utilization %"] = (df["Total Points Used"] / df["Total Earned Points"] * 100).round(1)
    return df


def build_gift_summary(retailers: list[dict]) -> pd.DataFrame:
    """Aggregate by gift type."""
    gift_data: dict[str, dict] = {}

    for r in retailers:
        for sel in r.get("selections", []):
            gift_info = sel.get("gifts_catalog", {})
            if not gift_info:
                continue

            name = gift_info.get("name", "Unknown")
            qty = sel.get("quantity", 1)
            pts = sel.get("points_used", 0)

            if name not in gift_data:
                gift_data[name] = {
                    "Gift": name,
                    "Units Selected": 0,
                    "Total Points": 0,
                    "Total Value (₹)": 0,
                }

            g = gift_data[name]
            g["Units Selected"] += qty
            g["Total Points"] += pts * qty

            if gift_info.get("is_flexible"):
                g["Total Value (₹)"] += pts * VOUCHER_POINTS_TO_INR
            else:
                g["Total Value (₹)"] += (gift_info.get("gift_value_inr", 0) or 0) * qty

    return pd.DataFrame(list(gift_data.values()))
