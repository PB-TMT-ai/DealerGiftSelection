-- =============================================================================
-- Migration: add dealer_details table for delivery contact info
-- Run this in the Supabase SQL Editor against the existing project.
-- Safe to re-run: uses IF NOT EXISTS.
-- =============================================================================

CREATE TABLE IF NOT EXISTS dealer_details (
  retailer_sf_id TEXT PRIMARY KEY REFERENCES retailers(sf_id) ON DELETE CASCADE,
  contact_name TEXT NOT NULL,
  phone TEXT NOT NULL,
  email TEXT,
  delivery_address TEXT NOT NULL,
  updated_by TEXT,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Refresh PostgREST schema cache so the new table is visible immediately.
NOTIFY pgrst, 'reload schema';
