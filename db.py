"""Supabase client and query helpers for the Q4 Gift Selection Portal."""

from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

_client: Client | None = None


def get_client() -> Client:
    """Return a singleton Supabase client."""
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        _client = create_client(url, key)
    return _client


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def get_user_by_pin(pin: str) -> dict | None:
    """Look up an app_user by PIN. Returns the row dict or None."""
    resp = get_client().table("app_users").select("*").eq("pin", pin).execute()
    if resp.data:
        return resp.data[0]
    return None


# ---------------------------------------------------------------------------
# Gift Catalog
# ---------------------------------------------------------------------------

def get_gifts_catalog() -> list[dict]:
    """Return all rows from gifts_catalog, ordered by id."""
    resp = get_client().table("gifts_catalog").select("*").order("id").execute()
    return resp.data or []


# ---------------------------------------------------------------------------
# Retailers
# ---------------------------------------------------------------------------

def get_retailers() -> list[dict]:
    """Return all retailers."""
    resp = get_client().table("retailers").select("*").order("retailer_name").execute()
    return resp.data or []


def get_retailer(sf_id: str) -> dict | None:
    """Return a single retailer by sf_id."""
    resp = (
        get_client()
        .table("retailers")
        .select("*")
        .eq("sf_id", sf_id)
        .limit(1)
        .execute()
    )
    if resp.data:
        return resp.data[0]
    return None


# ---------------------------------------------------------------------------
# Gift Selections
# ---------------------------------------------------------------------------

def get_selections_for_retailer(sf_id: str) -> list[dict]:
    """Return all gift_selections rows for a given retailer, with gift details."""
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
    Call the replace_selections RPC to atomically replace a retailer's gifts.

    ``selections`` is a list of dicts with keys: gift_id, points_used, quantity.
    Raises an exception if the RPC returns an error (e.g. over-budget, voucher < 250).
    """
    resp = get_client().rpc(
        "replace_selections",
        {
            "p_retailer": retailer_sf_id,
            "p_selections": json.dumps(selections),
            "p_user": user_name,
        },
    ).execute()
    return resp.data


# ---------------------------------------------------------------------------
# Admin Summaries
# ---------------------------------------------------------------------------

def get_all_retailers_with_selections() -> list[dict]:
    """
    Return every retailer with their selections joined.
    Used for the admin consolidated view.
    """
    retailers = get_retailers()
    selections = get_all_selections()

    # Group selections by retailer
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
