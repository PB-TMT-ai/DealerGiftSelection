-- =============================================================================
-- Q4 Dealer Scheme Gift Selection Portal — Database Schema
-- Run this in the Supabase SQL Editor before seeding or starting the app.
-- =============================================================================

-- ======================== TABLES ========================

-- Gift catalog (seeded from Sheet2 of source Excel)
CREATE TABLE IF NOT EXISTS gifts_catalog (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  slab TEXT,                          -- A-E; NULL for Amazon Voucher
  points_required INTEGER,            -- NULL for flexible-amount gifts (Voucher)
  gift_value_inr INTEGER,             -- NULL for Amazon Voucher (computed dynamically)
  is_flexible BOOLEAN DEFAULT FALSE,  -- TRUE only for Amazon Voucher
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Retailers (seeded from Data sheet of source Excel)
CREATE TABLE IF NOT EXISTS retailers (
  sf_id TEXT PRIMARY KEY,
  retailer_name TEXT NOT NULL,
  distributor_name TEXT NOT NULL,
  state_name TEXT,
  district_name TEXT,
  zone TEXT,
  distributor_self_counter TEXT,
  q4_volume NUMERIC,
  earned_points NUMERIC NOT NULL,
  eligible_slab TEXT,
  max_eligible_gift TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- One row per gift chosen; a retailer can have many rows
CREATE TABLE IF NOT EXISTS gift_selections (
  id BIGSERIAL PRIMARY KEY,
  retailer_sf_id TEXT NOT NULL REFERENCES retailers(sf_id) ON DELETE CASCADE,
  gift_id INTEGER NOT NULL REFERENCES gifts_catalog(id),
  points_used INTEGER NOT NULL,       -- fixed gift = catalog value; voucher = chosen amount
  quantity INTEGER NOT NULL DEFAULT 1,
  selected_by TEXT,                   -- SM/TM name from login
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- PIN-based users (internal tool — plain-text PINs are acceptable)
CREATE TABLE IF NOT EXISTS app_users (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  pin TEXT NOT NULL,                  -- 4-6 digit PIN
  role TEXT NOT NULL CHECK (role IN ('sm_tm', 'admin')),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ======================== INDEXES ========================

CREATE INDEX IF NOT EXISTS idx_retailers_distributor ON retailers(distributor_name);
CREATE INDEX IF NOT EXISTS idx_retailers_state ON retailers(state_name);
CREATE INDEX IF NOT EXISTS idx_retailers_zone ON retailers(zone);
CREATE INDEX IF NOT EXISTS idx_selections_retailer ON gift_selections(retailer_sf_id);

-- ======================== RPC FUNCTION ========================
-- Atomically replaces all gift selections for a retailer.
-- Validates:
--   1. Total points_used does not exceed retailer's earned_points
--   2. Any flexible gift (Amazon Voucher) has points_used >= 250 (VOUCHER_MIN_POINTS)
--
-- Parameters:
--   p_retailer  TEXT   — retailer sf_id
--   p_selections JSONB — array of {gift_id, points_used, quantity}
--   p_user       TEXT  — name of the SM/TM performing the save

CREATE OR REPLACE FUNCTION replace_selections(
  p_retailer TEXT,
  p_selections JSONB,
  p_user TEXT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_earned_points NUMERIC;
  v_total_points  NUMERIC := 0;
  v_sel           JSONB;
  v_gift_flexible BOOLEAN;
  v_points_used   INTEGER;
  v_quantity       INTEGER;
  v_voucher_min   CONSTANT INTEGER := 250;  -- Must match utils/constants.py VOUCHER_MIN_POINTS
BEGIN
  -- 1. Lock the retailer row and get earned_points
  SELECT earned_points INTO v_earned_points
  FROM retailers
  WHERE sf_id = p_retailer
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Retailer "%" not found', p_retailer;
  END IF;

  -- 2. Validate each selection and compute total
  FOR v_sel IN SELECT * FROM jsonb_array_elements(p_selections)
  LOOP
    v_points_used := (v_sel ->> 'points_used')::INTEGER;
    v_quantity    := COALESCE((v_sel ->> 'quantity')::INTEGER, 1);

    -- Check gift exists and whether it's flexible
    SELECT is_flexible INTO v_gift_flexible
    FROM gifts_catalog
    WHERE id = (v_sel ->> 'gift_id')::INTEGER;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'Gift ID % not found in catalog', (v_sel ->> 'gift_id');
    END IF;

    -- Voucher minimum check
    IF v_gift_flexible AND v_points_used < v_voucher_min THEN
      RAISE EXCEPTION 'Amazon Voucher minimum is % points (got %)', v_voucher_min, v_points_used;
    END IF;

    v_total_points := v_total_points + (v_points_used * v_quantity);
  END LOOP;

  -- 3. Total must not exceed earned points
  IF v_total_points > v_earned_points THEN
    RAISE EXCEPTION 'Total points (%) exceed earned points (%)', v_total_points, v_earned_points;
  END IF;

  -- 4. Atomic replace: delete existing, then insert new
  DELETE FROM gift_selections WHERE retailer_sf_id = p_retailer;

  INSERT INTO gift_selections (retailer_sf_id, gift_id, points_used, quantity, selected_by)
  SELECT
    p_retailer,
    (sel ->> 'gift_id')::INTEGER,
    (sel ->> 'points_used')::INTEGER,
    COALESCE((sel ->> 'quantity')::INTEGER, 1),
    p_user
  FROM jsonb_array_elements(p_selections) AS sel;
END;
$$;

-- ======================== SEED DATA ========================

-- Gift catalog (from Sheet2 of source Excel)
INSERT INTO gifts_catalog (name, slab, points_required, gift_value_inr, is_flexible) VALUES
  ('Foot massager',                          'A', 750,  3750,  FALSE),
  ('Sony sound bar woofer and speakers',     'B', 3000, 15000, FALSE),
  ('Robot Vacuum cleaner',                   'C', 4200, 21000, FALSE),
  ('Apple iPad',                             'D', 6800, 34000, FALSE),
  ('Samsung front-load washing machine',     'E', 7500, 37500, FALSE),
  ('Amazon Voucher',                         NULL, NULL, NULL,  TRUE)
ON CONFLICT (name) DO UPDATE SET
  slab            = EXCLUDED.slab,
  points_required = EXCLUDED.points_required,
  gift_value_inr  = EXCLUDED.gift_value_inr,
  is_flexible     = EXCLUDED.is_flexible;

-- Default app users
INSERT INTO app_users (name, pin, role) VALUES
  ('Admin',      '9999', 'admin'),
  ('Sales Team', '1111', 'sm_tm')
ON CONFLICT DO NOTHING;
