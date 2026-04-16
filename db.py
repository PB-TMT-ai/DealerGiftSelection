"""Supabase client and query helpers for the Q4 Gift Selection Portal.

When SUPABASE_URL is not set (or set to "demo"), the module operates in
DEMO MODE. If the source Excel file is available, all 292 real retailers
are loaded from it; otherwise 10 hardcoded sample retailers are used.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Mode detection
# ---------------------------------------------------------------------------
_DEMO_MODE = not os.environ.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL") == "demo"

_client = None

# Path to source Excel — prefer the newer consolidated file
_EXCEL_PATH: Path | None = None
for _candidate_name in [
    "FY 26 Q4 dealer scheme.xlsx",
    "Q4 Dealer Scheme_Point Based.xlsx",
]:
    for _dir in [Path(__file__).resolve().parent, Path(".")]:
        _candidate = _dir / _candidate_name
        if _candidate.exists():
            _EXCEL_PATH = _candidate
            break
    if _EXCEL_PATH:
        break


def get_client():
    """Return a singleton Supabase client (live mode only)."""
    global _client
    if _DEMO_MODE:
        return None
    if _client is None:
        from supabase import create_client
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        _client = create_client(url, key)
    return _client


# ============================================================================
# DEMO DATA — loaded from Excel when available, hardcoded fallback otherwise
# ============================================================================

_DEMO_USERS: list[dict] = [
    {"id": 1, "name": "Admin", "pin": "9999", "role": "admin"},
    {"id": 2, "name": "SM North", "pin": "1111", "role": "sm_tm"},
    {"id": 3, "name": "TM Central", "pin": "2222", "role": "sm_tm"},
]

# Mutable in-memory store for demo gift selections
_demo_selections: list[dict] = []
_demo_sel_id_counter: int = 0


_SLAB_THRESHOLDS: list[tuple[int, str]] = [
    (7500, "E"),
    (6800, "D"),
    (4200, "C"),
    (3000, "B"),
    (750, "A"),
]


def _compute_slab(earned_points: int) -> str | None:
    """Derive the eligible slab from earned points based on catalog thresholds."""
    for threshold, slab in _SLAB_THRESHOLDS:
        if earned_points >= threshold:
            return slab
    return None


def _load_from_excel() -> list[dict]:
    """
    Load retailers from the source Excel file.

    Supports two formats:
      - New format (FY 26): Sheet1 with header on row 3, 8 columns
      - Old format (Q4): Data sheet with header on row 1, 28 columns

    Returns list of retailer dicts.
    """
    import pandas as pd

    if _EXCEL_PATH is None:
        return []

    retailers: list[dict] = []
    seen_sf_ids: set[str] = set()

    # Detect file format by sheet names
    xl = pd.ExcelFile(_EXCEL_PATH)
    sheet_names = xl.sheet_names

    if "Sheet1" in sheet_names and "Data" not in sheet_names:
        # --- New format: FY 26 Q4 dealer scheme.xlsx ---
        # Header on row 3 (0-indexed: skiprows=2)
        # Cols: SF Id | Retailer Name | Distributor Name | State Name |
        #       Distributor self-counter | Zone | Q4 Vol | Points
        df = pd.read_excel(_EXCEL_PATH, sheet_name="Sheet1", skiprows=2)

        for _, row in df.iterrows():
            sf_id = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            if not sf_id or sf_id.lower() == "nan":
                continue
            if sf_id in seen_sf_ids:
                continue
            seen_sf_ids.add(sf_id)

            # Parse points — handle bad values like " -   "
            raw_pts = row.iloc[7]
            try:
                earned = int(round(float(raw_pts))) if pd.notna(raw_pts) else 0
            except (ValueError, TypeError):
                earned = 0

            raw_state = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else None
            if raw_state and raw_state not in ("0", "nan", "#N/A", "#n/a"):
                state_name = raw_state.title()
            else:
                state_name = None

            q4_vol = None
            try:
                q4_vol = float(row.iloc[6]) if pd.notna(row.iloc[6]) else None
            except (ValueError, TypeError):
                pass

            slab = _compute_slab(earned)

            retailers.append({
                "sf_id": sf_id,
                "retailer_name": str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else "",
                "distributor_name": str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else "",
                "state_name": state_name,
                "district_name": None,
                "distributor_self_counter": str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) else None,
                "zone": str(row.iloc[5]).strip() if pd.notna(row.iloc[5]) else None,
                "q4_volume": q4_vol,
                "earned_points": earned,
                "eligible_slab": slab,
                "max_eligible_gift": None,
            })

    elif "Data" in sheet_names:
        # --- Old format: Q4 Dealer Scheme_Point Based.xlsx ---
        df = pd.read_excel(_EXCEL_PATH, sheet_name="Data")

        for _, row in df.iterrows():
            sf_id = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            if not sf_id or sf_id.lower() == "nan":
                continue
            if sf_id in seen_sf_ids:
                continue
            seen_sf_ids.add(sf_id)

            earned = float(row.iloc[8]) if pd.notna(row.iloc[8]) else 0
            earned = int(round(earned))

            q4_vol = float(row.iloc[7]) if pd.notna(row.iloc[7]) else None

            raw_state = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else None
            if raw_state and raw_state not in ("0", "nan"):
                state_name = raw_state.title()
            else:
                state_name = None

            retailers.append({
                "sf_id": sf_id,
                "retailer_name": str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else "",
                "distributor_name": str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else "",
                "state_name": state_name,
                "district_name": str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) else None,
                "distributor_self_counter": str(row.iloc[5]).strip() if pd.notna(row.iloc[5]) else None,
                "zone": str(row.iloc[6]).strip() if pd.notna(row.iloc[6]) else None,
                "q4_volume": q4_vol,
                "earned_points": earned,
                "eligible_slab": str(row.iloc[26]).strip() if pd.notna(row.iloc[26]) else None,
                "max_eligible_gift": str(row.iloc[27]).strip() if pd.notna(row.iloc[27]) else None,
            })

    return retailers


# --- Hardcoded fallback (used when Excel file is not available) ---

_FALLBACK_CATALOG: list[dict] = [
    {"id": 1, "name": "Foot massager", "slab": "A", "points_required": 750, "gift_value_inr": 3750, "is_flexible": False},
    {"id": 2, "name": "Sony - sound bar woofer and speakers", "slab": "B", "points_required": 3000, "gift_value_inr": 15000, "is_flexible": False},
    {"id": 3, "name": "Robot Vacuum cleaner", "slab": "C", "points_required": 4200, "gift_value_inr": 21000, "is_flexible": False},
    {"id": 4, "name": "Apple iPad", "slab": "D", "points_required": 6800, "gift_value_inr": 34000, "is_flexible": False},
    {"id": 5, "name": "Samsung front-load washing machine", "slab": "E", "points_required": 7500, "gift_value_inr": 37500, "is_flexible": False},
    {"id": 6, "name": "Amazon Voucher", "slab": None, "points_required": None, "gift_value_inr": None, "is_flexible": True},
]

_FALLBACK_RETAILERS: list[dict] = [
    {"sf_id": "SF001", "retailer_name": "Sharma Electronics", "distributor_name": "ABC Distributors", "state_name": "Maharashtra", "district_name": "Mumbai", "zone": "West", "distributor_self_counter": "Self", "q4_volume": 15000, "earned_points": 7500, "eligible_slab": "E", "max_eligible_gift": "Samsung front-load washing machine"},
    {"sf_id": "SF002", "retailer_name": "Gupta Traders", "distributor_name": "XYZ Distributors", "state_name": "Uttar Pradesh", "district_name": "Lucknow", "zone": "North", "distributor_self_counter": "Counter", "q4_volume": 8000, "earned_points": 4200, "eligible_slab": "C", "max_eligible_gift": "Robot Vacuum cleaner"},
    {"sf_id": "SF003", "retailer_name": "Patel Agencies", "distributor_name": "DEF Distributors", "state_name": "Gujarat", "district_name": "Ahmedabad", "zone": "West", "distributor_self_counter": "Self", "q4_volume": 5000, "earned_points": 3000, "eligible_slab": "B", "max_eligible_gift": "Sony - sound bar woofer and speakers"},
    {"sf_id": "SF004", "retailer_name": "Singh Hardware", "distributor_name": "GHI Distributors", "state_name": "Punjab", "district_name": "Ludhiana", "zone": "North", "distributor_self_counter": "Counter", "q4_volume": 12000, "earned_points": 6800, "eligible_slab": "D", "max_eligible_gift": "Apple iPad"},
    {"sf_id": "SF005", "retailer_name": "Reddy Enterprises", "distributor_name": "JKL Distributors", "state_name": "Telangana", "district_name": "Hyderabad", "zone": "South", "distributor_self_counter": "Self", "q4_volume": 3000, "earned_points": 1500, "eligible_slab": "A", "max_eligible_gift": "Foot massager"},
    {"sf_id": "SF006", "retailer_name": "Das & Sons", "distributor_name": "MNO Distributors", "state_name": "West Bengal", "district_name": "Kolkata", "zone": "East", "distributor_self_counter": "Counter", "q4_volume": 6000, "earned_points": 3750, "eligible_slab": "B", "max_eligible_gift": "Sony - sound bar woofer and speakers"},
    {"sf_id": "SF007", "retailer_name": "Iyer Store", "distributor_name": "PQR Distributors", "state_name": "Tamil Nadu", "district_name": "Chennai", "zone": "South", "distributor_self_counter": "Self", "q4_volume": 2000, "earned_points": 750, "eligible_slab": "A", "max_eligible_gift": "Foot massager"},
    {"sf_id": "SF008", "retailer_name": "Khan Retail", "distributor_name": "ABC Distributors", "state_name": "Maharashtra", "district_name": "Pune", "zone": "West", "distributor_self_counter": "Counter", "q4_volume": 10000, "earned_points": 5000, "eligible_slab": "C", "max_eligible_gift": "Robot Vacuum cleaner"},
    {"sf_id": "SF009", "retailer_name": "Joshi Mart", "distributor_name": "XYZ Distributors", "state_name": "Rajasthan", "district_name": "Jaipur", "zone": "North", "distributor_self_counter": "Self", "q4_volume": 500, "earned_points": 200, "eligible_slab": "A", "max_eligible_gift": "Foot massager"},
    {"sf_id": "SF010", "retailer_name": "Menon Supplies", "distributor_name": "JKL Distributors", "state_name": "Kerala", "district_name": "Kochi", "zone": "South", "distributor_self_counter": "Self", "q4_volume": 4500, "earned_points": 2500, "eligible_slab": "B", "max_eligible_gift": "Sony - sound bar woofer and speakers"},
]

# --- Load demo data (Excel if available, else fallback) ---

_excel_retailers = _load_from_excel()

_DEMO_CATALOG: list[dict] = _FALLBACK_CATALOG
_DEMO_RETAILERS: list[dict] = _excel_retailers if _excel_retailers else _FALLBACK_RETAILERS


def _catalog_by_id() -> dict[int, dict]:
    return {g["id"]: g for g in _DEMO_CATALOG}


# ============================================================================
# PUBLIC API — each function branches on _DEMO_MODE
# ============================================================================

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def get_user_by_pin(pin: str) -> dict | None:
    """Look up an app_user by PIN. Returns the row dict or None."""
    if _DEMO_MODE:
        for u in _DEMO_USERS:
            if u["pin"] == pin:
                return u
        return None

    resp = get_client().table("app_users").select("*").eq("pin", pin).execute()
    return resp.data[0] if resp.data else None


# ---------------------------------------------------------------------------
# Gift Catalog
# ---------------------------------------------------------------------------

def get_gifts_catalog() -> list[dict]:
    """Return all rows from gifts_catalog, ordered by id."""
    if _DEMO_MODE:
        return list(_DEMO_CATALOG)

    resp = get_client().table("gifts_catalog").select("*").order("id").execute()
    return resp.data or []


# ---------------------------------------------------------------------------
# Retailers
# ---------------------------------------------------------------------------

def get_retailers() -> list[dict]:
    """Return all retailers."""
    if _DEMO_MODE:
        return sorted(_DEMO_RETAILERS, key=lambda r: r["retailer_name"])

    resp = get_client().table("retailers").select("*").order("retailer_name").execute()
    return resp.data or []


def get_retailer(sf_id: str) -> dict | None:
    """Return a single retailer by sf_id."""
    if _DEMO_MODE:
        for r in _DEMO_RETAILERS:
            if r["sf_id"] == sf_id:
                return r
        return None

    resp = (
        get_client()
        .table("retailers")
        .select("*")
        .eq("sf_id", sf_id)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


# ---------------------------------------------------------------------------
# Gift Selections
# ---------------------------------------------------------------------------

def get_selections_for_retailer(sf_id: str) -> list[dict]:
    """Return all gift_selections rows for a given retailer, with gift details."""
    if _DEMO_MODE:
        cat = _catalog_by_id()
        return [
            {**s, "gifts_catalog": cat.get(s["gift_id"], {})}
            for s in _demo_selections
            if s["retailer_sf_id"] == sf_id
        ]

    resp = (
        get_client()
        .table("gift_selections")
        .select("*, gifts_catalog(*)")
        .eq("retailer_sf_id", sf_id)
        .execute()
    )
    return resp.data or []


def get_all_selections() -> list[dict]:
    """Return every gift_selections row with gift catalog joined."""
    if _DEMO_MODE:
        cat = _catalog_by_id()
        return [
            {**s, "gifts_catalog": cat.get(s["gift_id"], {})}
            for s in _demo_selections
        ]

    resp = (
        get_client()
        .table("gift_selections")
        .select("*, gifts_catalog(*)")
        .execute()
    )
    return resp.data or []


def get_points_used_per_retailer() -> dict[str, int]:
    """Return a dict mapping sf_id -> total points used across all selections."""
    selections = get_all_selections()
    usage: dict[str, int] = {}
    for sel in selections:
        sf_id = sel["retailer_sf_id"]
        pts = sel["points_used"] * sel.get("quantity", 1)
        usage[sf_id] = usage.get(sf_id, 0) + pts
    return usage


def replace_selections(
    retailer_sf_id: str,
    selections: list[dict],
    user_name: str,
) -> dict[str, Any]:
    """
    Atomically replace a retailer's gift selections.

    In demo mode, validates and stores in memory.
    In live mode, calls the replace_selections Postgres RPC.
    """
    if _DEMO_MODE:
        return _demo_replace_selections(retailer_sf_id, selections, user_name)

    resp = get_client().rpc(
        "replace_selections",
        {
            "p_retailer": retailer_sf_id,
            "p_selections": json.dumps(selections),
            "p_user": user_name,
        },
    ).execute()
    return resp.data


def _demo_replace_selections(
    retailer_sf_id: str,
    selections: list[dict],
    user_name: str,
) -> dict:
    """In-memory replacement with same validation as the Postgres RPC."""
    global _demo_sel_id_counter

    from utils.constants import VOUCHER_MIN_POINTS

    # Find retailer
    retailer = get_retailer(retailer_sf_id)
    if not retailer:
        raise ValueError(f'Retailer "{retailer_sf_id}" not found')

    earned = int(retailer["earned_points"])
    cat = _catalog_by_id()

    # Validate
    total = 0
    for sel in selections:
        gift = cat.get(sel["gift_id"])
        if not gift:
            raise ValueError(f"Gift ID {sel['gift_id']} not found in catalog")

        pts = sel["points_used"]
        qty = sel.get("quantity", 1)

        if gift["is_flexible"] and pts < VOUCHER_MIN_POINTS:
            raise ValueError(
                f"Amazon Voucher minimum is {VOUCHER_MIN_POINTS} points (got {pts})"
            )
        total += pts * qty

    if total > earned:
        raise ValueError(
            f"Total points ({total}) exceed earned points ({earned})"
        )

    # Atomic replace in memory
    _demo_selections[:] = [
        s for s in _demo_selections if s["retailer_sf_id"] != retailer_sf_id
    ]

    for sel in selections:
        _demo_sel_id_counter += 1
        _demo_selections.append({
            "id": _demo_sel_id_counter,
            "retailer_sf_id": retailer_sf_id,
            "gift_id": sel["gift_id"],
            "points_used": sel["points_used"],
            "quantity": sel.get("quantity", 1),
            "selected_by": user_name,
            "notes": None,
        })

    return {"ok": True}


# ---------------------------------------------------------------------------
# Admin Summaries
# ---------------------------------------------------------------------------

def get_all_retailers_with_selections() -> list[dict]:
    """Return every retailer with their selections joined."""
    retailers = get_retailers()
    selections = get_all_selections()

    sel_by_retailer: dict[str, list[dict]] = {}
    for sel in selections:
        sf_id = sel["retailer_sf_id"]
        sel_by_retailer.setdefault(sf_id, []).append(sel)

    for r in retailers:
        r["selections"] = sel_by_retailer.get(r["sf_id"], [])
        r["points_used"] = sum(
            s["points_used"] * s.get("quantity", 1) for s in r["selections"]
        )
        r["balance"] = int(r["earned_points"]) - r["points_used"]

    return retailers
