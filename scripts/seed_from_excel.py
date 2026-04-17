#!/usr/bin/env python3
"""
Seed Supabase tables from the Q4 dealer scheme Excel workbook.

Usage:
    python scripts/seed_from_excel.py [path_to_excel]
    python scripts/seed_from_excel.py --import-current-gifts [path_to_excel]

Two workbook formats are supported:
  - New format (FY 26 …): ``Costing`` sheet for catalog, ``Dealer data`` for retailers.
  - Old format (Q4 Dealer Scheme_Point_Based): ``Sheet2`` for catalog, ``Data`` for retailers.

- Seeds default app_users
- Idempotent: safe to re-run.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# Ensure project root is on sys.path so we can import db
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv()

from db import get_client  # noqa: E402


def normalize_name(name: str) -> str:
    """Lowercase, strip whitespace and punctuation for fuzzy matching."""
    return re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()


# Physical-gift point derivation for the new Costing sheet, which only
# carries name + INR value. 5 INR per point matches the historical catalog;
# slabs are assigned A/B/C/... in ascending INR order.
_PHYSICAL_INR_PER_POINT = 5
_SLAB_LETTERS = ["A", "B", "C", "D", "E", "F", "G"]


def _upsert_catalog_item(client, record: dict, catalog_map: dict[str, int]) -> None:
    resp = client.table("gifts_catalog").upsert(
        record, on_conflict="name"
    ).execute()
    if resp.data:
        catalog_map[normalize_name(record["name"])] = resp.data[0]["id"]


def seed_gift_catalog(client, excel_path: str) -> dict[str, int]:
    """
    Upsert gifts_catalog from the workbook. Handles both formats:
      - New: ``Costing`` sheet (name + INR, points derived).
      - Old: ``Sheet2`` (points, INR, name, slab — all explicit).

    Returns ``{normalized_name: id}``.
    """
    xl = pd.ExcelFile(excel_path)
    sheet_names = xl.sheet_names
    catalog_map: dict[str, int] = {}

    if "Costing" in sheet_names:
        # --- New format: skip the two blank rows + header row above data ---
        df = pd.read_excel(
            excel_path, sheet_name="Costing", skiprows=3, header=None
        )
        print(f"  Costing: {len(df)} rows")

        physical_items: list[tuple[str, int]] = []
        voucher_seen = False

        for _, row in df.iterrows():
            name = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            if not name or name.lower() == "nan":
                continue
            try:
                inr = int(float(row.iloc[1])) if pd.notna(row.iloc[1]) else None
            except (ValueError, TypeError):
                continue
            if inr is None:
                continue

            if "amazon" in name.lower():
                voucher_seen = True
            else:
                physical_items.append((name, inr))

        physical_items.sort(key=lambda t: t[1])
        for i, (name, inr) in enumerate(physical_items):
            slab = _SLAB_LETTERS[i] if i < len(_SLAB_LETTERS) else None
            _upsert_catalog_item(
                client,
                {
                    "name": name,
                    "slab": slab,
                    "points_required": int(inr / _PHYSICAL_INR_PER_POINT),
                    "gift_value_inr": inr,
                    "is_flexible": False,
                },
                catalog_map,
            )

        # Always ensure the voucher row exists, even if Costing omits it.
        _upsert_catalog_item(
            client,
            {
                "name": "Amazon Voucher",
                "slab": None,
                "points_required": None,
                "gift_value_inr": None,
                "is_flexible": True,
            },
            catalog_map,
        )
        _ = voucher_seen
    else:
        # --- Old format: Sheet2 with explicit Points | INR | Name | Slab ---
        df = pd.read_excel(excel_path, sheet_name="Sheet2")
        print(f"  Sheet2: {len(df)} rows")
        df.columns = [str(c).strip() for c in df.columns]

        for _, row in df.iterrows():
            name = str(row.iloc[2]).strip()
            if not name or name.lower() == "nan":
                continue

            points_required = int(row.iloc[0]) if pd.notna(row.iloc[0]) else None
            gift_value_inr = int(row.iloc[1]) if pd.notna(row.iloc[1]) else None
            slab = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else None
            is_flexible = name.lower().startswith("amazon")

            _upsert_catalog_item(
                client,
                {
                    "name": name,
                    "slab": slab if slab and slab.lower() != "nan" else None,
                    "points_required": points_required,
                    "gift_value_inr": gift_value_inr,
                    "is_flexible": is_flexible,
                },
                catalog_map,
            )

        _upsert_catalog_item(
            client,
            {
                "name": "Amazon Voucher",
                "slab": None,
                "points_required": None,
                "gift_value_inr": None,
                "is_flexible": True,
            },
            catalog_map,
        )

    print(f"  Upserted {len(catalog_map)} catalog items")
    return catalog_map


def seed_retailers(client, excel_path: str) -> int:
    """
    Parse the retailer sheet and upsert retailers. Supports:
      - New format: ``Dealer data`` sheet, header on row 3 (skiprows=2).
      - Old format: ``Data`` sheet, header on row 1.
    """
    xl = pd.ExcelFile(excel_path)
    sheet_names = xl.sheet_names

    if "Dealer data" in sheet_names:
        df = pd.read_excel(excel_path, sheet_name="Dealer data", skiprows=2)
        print(f"  Dealer data sheet: {len(df)} rows")
    else:
        df = pd.read_excel(excel_path, sheet_name="Data")
        print(f"  Data sheet: {len(df)} rows")

    df.columns = [str(c).strip() for c in df.columns]

    # Build a column mapping — try to detect common header variations
    col_map = {}
    for c in df.columns:
        cl = c.lower()
        if "sf" in cl and "id" in cl:
            col_map["sf_id"] = c
        elif "retailer" in cl and "name" in cl:
            col_map["retailer_name"] = c
        elif "distributor" in cl and ("name" in cl or cl == "distributor"):
            col_map["distributor_name"] = c
        elif "state" in cl:
            col_map["state_name"] = c
        elif "district" in cl:
            col_map["district_name"] = c
        elif "zone" in cl:
            col_map["zone"] = c
        elif "self" in cl and "counter" in cl:
            col_map["distributor_self_counter"] = c
        elif "q4" in cl and "vol" in cl:
            col_map["q4_volume"] = c
        elif ("earned" in cl and "point" in cl) or cl == "points":
            col_map["earned_points"] = c
        elif "eligible" in cl and "slab" in cl:
            col_map["eligible_slab"] = c
        elif "max" in cl and "gift" in cl:
            col_map["max_eligible_gift"] = c
        elif "current" in cl and "gift" in cl:
            col_map["current_gift"] = c

    if "sf_id" not in col_map:
        print("  ERROR: Could not find SF ID column. Available:", list(df.columns))
        return 0

    count = 0
    for _, row in df.iterrows():
        sf_id = str(row.get(col_map.get("sf_id", ""), "")).strip()
        if not sf_id or sf_id.lower() == "nan":
            continue

        earned = row.get(col_map.get("earned_points", ""), 0)
        if pd.isna(earned):
            earned = 0

        record = {
            "sf_id": sf_id,
            "retailer_name": str(row.get(col_map.get("retailer_name", ""), "")).strip(),
            "distributor_name": str(row.get(col_map.get("distributor_name", ""), "")).strip(),
            "state_name": _safe_str(row.get(col_map.get("state_name", ""))),
            "district_name": _safe_str(row.get(col_map.get("district_name", ""))),
            "zone": _safe_str(row.get(col_map.get("zone", ""))),
            "distributor_self_counter": _safe_str(row.get(col_map.get("distributor_self_counter", ""))),
            "q4_volume": float(row.get(col_map.get("q4_volume", ""), 0)) if pd.notna(row.get(col_map.get("q4_volume", ""), None)) else None,
            "earned_points": float(earned),
            "eligible_slab": _safe_str(row.get(col_map.get("eligible_slab", ""))),
            "max_eligible_gift": _safe_str(row.get(col_map.get("max_eligible_gift", ""))),
        }

        client.table("retailers").upsert(record, on_conflict="sf_id").execute()
        count += 1

    print(f"  Upserted {count} retailers")
    return count


def seed_current_gifts(client, excel_path: str, catalog_map: dict[str, int]) -> int:
    """Import 'Current gift' column as gift_selections. Fuzzy-matches to catalog."""
    df = pd.read_excel(excel_path, sheet_name="Data")
    df.columns = [str(c).strip() for c in df.columns]

    # Find relevant columns
    sf_col = None
    gift_col = None
    for c in df.columns:
        cl = c.lower()
        if "sf" in cl and "id" in cl:
            sf_col = c
        elif "current" in cl and "gift" in cl:
            gift_col = c

    if not sf_col or not gift_col:
        print("  Could not find SF ID or Current Gift column — skipping import")
        return 0

    imported = 0
    unmatched: list[str] = []

    for _, row in df.iterrows():
        sf_id = str(row.get(sf_col, "")).strip()
        gift_name = str(row.get(gift_col, "")).strip()
        if not sf_id or sf_id.lower() == "nan" or not gift_name or gift_name.lower() == "nan":
            continue

        normalized = normalize_name(gift_name)
        gift_id = catalog_map.get(normalized)

        if gift_id is None:
            # Try partial match
            for cat_name, cat_id in catalog_map.items():
                if normalized in cat_name or cat_name in normalized:
                    gift_id = cat_id
                    break

        if gift_id is None:
            unmatched.append(gift_name)
            continue

        # Get points_required from catalog
        resp = client.table("gifts_catalog").select("points_required, is_flexible").eq("id", gift_id).execute()
        if not resp.data:
            continue

        gift_data = resp.data[0]
        points_used = gift_data["points_required"] or 0

        client.table("gift_selections").upsert(
            {
                "retailer_sf_id": sf_id,
                "gift_id": gift_id,
                "points_used": points_used,
                "quantity": 1,
                "selected_by": "import",
                "notes": "Imported from Excel - Current gift column",
            },
            on_conflict="retailer_sf_id,gift_id",
            ignore_duplicates=True,
        ).execute()
        imported += 1

    if unmatched:
        unique_unmatched = sorted(set(unmatched))
        print(f"  WARNING: {len(unique_unmatched)} unmatched gift names:", file=sys.stderr)
        for name in unique_unmatched:
            print(f"    - {name}", file=sys.stderr)

    print(f"  Imported {imported} current gift selections")
    return imported


def seed_app_users(client) -> None:
    """Seed default app users. Idempotent via ON CONFLICT."""
    users = [
        {"name": "Admin", "pin": "9999", "role": "admin"},
        {"name": "Sales Team", "pin": "1111", "role": "sm_tm"},
    ]
    for user in users:
        client.table("app_users").upsert(user, on_conflict="pin").execute()
    print(f"  Seeded {len(users)} app users")


def _safe_str(val) -> str | None:
    """Convert a value to string, returning None for NaN/empty."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    return s if s and s.lower() != "nan" else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Supabase from Q4 Excel")
    parser.add_argument(
        "excel_path",
        nargs="?",
        default="./FY 26 Q4 dealer scheme_v2.xlsx",
        help="Path to the source Excel file",
    )
    parser.add_argument(
        "--import-current-gifts",
        action="store_true",
        help="Import the 'Current gift' column as gift_selections",
    )
    args = parser.parse_args()

    excel_path = args.excel_path
    if not Path(excel_path).exists():
        print(f"ERROR: Excel file not found at {excel_path}")
        sys.exit(1)

    client = get_client()

    print("1. Seeding gift catalog...")
    catalog_map = seed_gift_catalog(client, excel_path)

    print("2. Seeding retailers...")
    seed_retailers(client, excel_path)

    print("3. Seeding app users...")
    seed_app_users(client)

    if args.import_current_gifts:
        print("4. Importing current gift selections...")
        seed_current_gifts(client, excel_path, catalog_map)

    print("\nDone! Seeding complete.")


if __name__ == "__main__":
    main()
