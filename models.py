"""Pydantic v2 schemas for the Q4 Dealer Scheme Gift Selection Portal."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Gift(BaseModel):
    id: int
    name: str
    slab: Optional[str] = None
    points_required: Optional[int] = None
    gift_value_inr: Optional[int] = None
    is_flexible: bool = False


class Retailer(BaseModel):
    sf_id: str
    retailer_name: str
    distributor_name: str
    state_name: Optional[str] = None
    district_name: Optional[str] = None
    zone: Optional[str] = None
    distributor_self_counter: Optional[str] = None
    q4_volume: Optional[float] = None
    earned_points: float
    eligible_slab: Optional[str] = None
    max_eligible_gift: Optional[str] = None


class GiftSelection(BaseModel):
    id: Optional[int] = None
    retailer_sf_id: str
    gift_id: int
    points_used: int
    quantity: int = 1
    selected_by: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SelectionInput(BaseModel):
    """Payload item for the replace_selections RPC call."""
    gift_id: int
    points_used: int = Field(ge=1)
    quantity: int = Field(ge=1, default=1)


class User(BaseModel):
    id: int
    name: str
    pin: str
    role: str  # 'sm_tm' or 'admin'


class FilterParams(BaseModel):
    """Optional filters for retailer listing."""
    distributor_name: Optional[str] = None
    states: Optional[list[str]] = None
    zones: Optional[list[str]] = None
    slabs: Optional[list[str]] = None
    retailer_search: Optional[str] = None
    min_balance: Optional[int] = None
    max_balance: Optional[int] = None
    has_selections: Optional[bool] = None  # None = All, True = Yes, False = No
