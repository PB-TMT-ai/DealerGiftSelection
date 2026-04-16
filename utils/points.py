"""
Gift combination suggestion algorithm and point validation utilities.

Brute-force approach: 5 physical gifts × qty 0-3 = 4^5 = 1024 combos.
Trivially fast — no optimization needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Optional

from utils.constants import VOUCHER_MIN_POINTS, VOUCHER_POINTS_TO_INR


@dataclass
class ComboItem:
    gift_id: int
    gift_name: str
    points_required: int
    quantity: int
    gift_value_inr: int = 0
    is_voucher: bool = False


@dataclass
class Combo:
    items: list[ComboItem] = field(default_factory=list)
    voucher_points: int = 0
    total_points: int = 0
    utilization: float = 0.0

    @property
    def voucher_inr(self) -> int:
        return self.voucher_points * VOUCHER_POINTS_TO_INR

    @property
    def total_value_inr(self) -> int:
        physical = sum(it.gift_value_inr * it.quantity for it in self.items if not it.is_voucher)
        return physical + self.voucher_inr

    @property
    def item_count(self) -> int:
        return sum(it.quantity for it in self.items)


def suggest_combinations(
    balance: int,
    catalog: list[dict],
    max_suggestions: int = 3,
    max_qty: int = 3,
) -> list[Combo]:
    """
    Return up to max_suggestions combos whose total points <= balance,
    ranked by:
      1. Utilization (used/balance), highest first
      2. Fewer items preferred when utilization ties

    Voucher rules:
    - Append voucher ONLY if leftover >= VOUCHER_MIN_POINTS (250)
    - If leftover < VOUCHER_MIN_POINTS, those points remain unredeemed
    - A standalone voucher suggestion is valid if balance >= VOUCHER_MIN_POINTS
    - Voucher INR value = leftover_points * VOUCHER_POINTS_TO_INR
    """
    if balance <= 0:
        return []

    physical = [g for g in catalog if not g.get("is_flexible") and g.get("points_required")]
    voucher = next((g for g in catalog if g.get("is_flexible")), None)

    # Edge case: can't afford cheapest physical gift
    cheapest_physical = min((g["points_required"] for g in physical), default=float("inf"))

    if balance < cheapest_physical and balance < VOUCHER_MIN_POINTS:
        # Can't afford anything
        return []

    combos: list[Combo] = []

    # Generate all qty combos for physical gifts (0 to max_qty each)
    qty_ranges = [range(0, max_qty + 1) for _ in physical]

    for qtys in product(*qty_ranges):
        physical_total = sum(g["points_required"] * q for g, q in zip(physical, qtys))
        if physical_total > balance:
            continue

        leftover = balance - physical_total

        # Build physical items for this combo
        items = []
        for g, q in zip(physical, qtys):
            if q > 0:
                items.append(ComboItem(
                    gift_id=g["id"],
                    gift_name=g["name"],
                    points_required=g["points_required"],
                    quantity=q,
                    gift_value_inr=g.get("gift_value_inr", 0),
                    is_voucher=False,
                ))

        # Option A: physical gifts only (if any selected)
        if items:
            combos.append(Combo(
                items=list(items),
                voucher_points=0,
                total_points=physical_total,
                utilization=physical_total / balance if balance > 0 else 0,
            ))

        # Option B: physical gifts + voucher for leftover
        if voucher and leftover >= VOUCHER_MIN_POINTS:
            voucher_item = ComboItem(
                gift_id=voucher["id"],
                gift_name=voucher["name"],
                points_required=leftover,
                quantity=1,
                gift_value_inr=leftover * VOUCHER_POINTS_TO_INR,
                is_voucher=True,
            )
            combo_with_voucher = Combo(
                items=list(items) + [voucher_item],
                voucher_points=leftover,
                total_points=physical_total + leftover,
                utilization=(physical_total + leftover) / balance if balance > 0 else 0,
            )
            combos.append(combo_with_voucher)

    # Sort: highest utilization first, then fewest items on tie
    combos.sort(key=lambda c: (-c.utilization, c.item_count))

    # Deduplicate by gift composition
    seen: set[tuple] = set()
    unique: list[Combo] = []
    for c in combos:
        key = tuple(
            sorted((it.gift_id, it.quantity) for it in c.items)
        ) + (c.voucher_points,)
        if key not in seen:
            seen.add(key)
            unique.append(c)
        if len(unique) >= max_suggestions:
            break

    return unique


def validate_selection_total(
    selections: list[dict],
    earned_points: int,
    catalog: list[dict],
) -> tuple[bool, str]:
    """
    Validate a set of selections against the earned points.

    Returns (is_valid, error_message).
    """
    if not selections:
        return False, "No items selected"

    # Build catalog lookup
    catalog_map = {g["id"]: g for g in catalog}
    total = 0

    for sel in selections:
        gift = catalog_map.get(sel["gift_id"])
        if not gift:
            return False, f"Unknown gift ID: {sel['gift_id']}"

        pts = sel["points_used"]
        qty = sel.get("quantity", 1)

        if gift.get("is_flexible"):
            # Voucher validation
            if pts < VOUCHER_MIN_POINTS:
                return False, f"Amazon Voucher minimum is {VOUCHER_MIN_POINTS} points (got {pts})"
        else:
            # Physical gift: points must match catalog
            if pts != gift["points_required"]:
                return False, f"Points mismatch for {gift['name']}: expected {gift['points_required']}, got {pts}"

        total += pts * qty

    if total > earned_points:
        return False, f"Total points ({total:,}) exceed earned points ({earned_points:,})"

    return True, ""
