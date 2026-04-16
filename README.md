# Q4 Dealer Scheme Gift Selection Portal

Internal tool for Sales Managers and Territory Managers to help dealer-retailers redeem earned Q4 scheme points for physical gifts and Amazon Vouchers.

## Tech Stack

- **Frontend:** Streamlit
- **Database:** Supabase (Postgres)
- **Language:** Python 3.11+
- **Validation:** Pydantic v2
- **Excel I/O:** openpyxl + pandas

## Quick Start (Demo Mode)

No database setup needed. The app runs with 10 sample retailers in-memory.

```bash
pip install -r requirements.txt
streamlit run app.py
```

### Deploy to Streamlit Community Cloud

1. Push code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. New app -> select repo, branch, `app.py`
4. Deploy (no secrets needed for demo mode)

To connect a live Supabase database, add these secrets in the Streamlit Cloud dashboard:

```
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-anon-or-service-key"
```

## Full Setup (with Supabase)

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-or-service-key
```

### 3. Create database schema

Open the Supabase SQL Editor and run `supabase/schema.sql`. This creates:

- `gifts_catalog` — 5 physical gifts + Amazon Voucher
- `retailers` — dealer-retailer master data
- `gift_selections` — redemption records (many-per-retailer)
- `app_users` — PIN-based login users
- `replace_selections()` — atomic RPC for save with server-side validation

### 4. Seed data from Excel

```bash
python scripts/seed_from_excel.py ./Q4_Dealer_Scheme_Point_Based.xlsx
```

To also import existing "Current gift" selections:

```bash
python scripts/seed_from_excel.py --import-current-gifts ./Q4_Dealer_Scheme_Point_Based.xlsx
```

The script is idempotent — safe to re-run.

### 5. Run the app

```bash
streamlit run app.py
```

## Test Accounts

| Name       | PIN  | Role   | Access                           |
|------------|------|--------|----------------------------------|
| Admin      | 9999 | admin  | Gift Selection + Admin Dashboard |
| SM North   | 1111 | sm_tm  | Gift Selection only              |
| TM Central | 2222 | sm_tm  | Gift Selection only              |

## Features

### Gift Selection (SM/TM + Admin)
- Filter retailers by distributor, state, zone, slab, name search, selection status
- View retailer point balances
- Select multiple physical gifts + Amazon Voucher per retailer
- Live balance math — prevents over-redemption at UI level
- Combo suggestions ranked by point utilization
- Atomic save via Postgres RPC (server-side validation)

### Admin Dashboard
- KPI summary: total retailers, points utilized, utilization %
- Consolidated table with gift breakdowns
- Zone-wise, state-wise, and gift-wise summary tables
- Excel export with 4 styled sheets

### Amazon Voucher Rules
- Minimum: 250 points
- Conversion: 1 point = ₹4
- Can combine with physical gifts
- If remaining balance < 250 after physical selections, voucher is unavailable

### Demo Mode
When `SUPABASE_URL` is not set, the app runs with in-memory sample data:
- 10 retailers across 4 zones and 9 states
- Full gift catalog (5 physical + Amazon Voucher)
- All validation rules enforced identically to live mode
- Selections persist in memory during the session

## Project Structure

```
app.py                    # Entry point, PIN login
auth.py                   # PIN verification + lockout
db.py                     # Supabase client + demo mode
models.py                 # Pydantic v2 schemas
pages/
  1_Gift_Selection.py     # SM/TM retailer + gift picker view
  2_Consolidated_Admin.py # Admin dashboard + export
components/
  retailer_table.py       # Filterable retailer grid
  gift_picker.py          # Gift selection UI with balance math
  suggestions.py          # Combo suggestion panel
utils/
  constants.py            # Business rule constants
  points.py               # Suggestion algorithm + validation
  excel_export.py         # Excel workbook generation
supabase/
  schema.sql              # Full DDL + RPC + seed data
scripts/
  seed_from_excel.py      # Excel -> Supabase seeder
```
