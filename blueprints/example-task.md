# Blueprint: Add New Gift to Catalog

## Goal

Add a new physical gift option to the catalog so retailers can select it.

## Inputs Required

- gift_name: str (display name)
- slab: str (A-E)
- points_required: int (point cost)
- gift_value_inr: int (rupee value)

## Steps

1. Add row to `gifts_catalog` table in Supabase (or to `_DEMO_CATALOG` in `db.py` for demo mode)
2. Update `supabase/schema.sql` seed data section to include the new gift
3. Verify the gift appears in the Gift Selection picker
4. Verify the suggestion algorithm includes the new gift in combos
5. Verify the Admin dashboard shows the new gift in Gift Summary

## Scripts to Use

1. `scripts/seed_from_excel.py` — if adding from Excel Sheet2 update
2. Direct Supabase SQL insert — for one-off additions

## Edge Cases

- Gift name must be unique (UNIQUE constraint on `gifts_catalog.name`)
- Points must be > 0 for physical gifts
- If re-running seed script, use upsert to avoid duplicates

## Known Issues

- Demo mode catalog is hardcoded in `db.py` — must update `_DEMO_CATALOG` list manually
