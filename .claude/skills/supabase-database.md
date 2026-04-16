# Supabase Database Skill (Python)

## Setup

- `SUPABASE_URL` and `SUPABASE_KEY` from environment
- Use `python-dotenv` to load `.env`
- Singleton client pattern in `db.py`

## Client Setup

```python
from supabase import create_client, Client
from dotenv import load_dotenv
import os

load_dotenv()
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
```

## Error Handling

```python
resp = client.table("retailers").select("*").execute()
# supabase-py raises exceptions on HTTP errors
# Always wrap in try/except for user-facing code
try:
    data = resp.data
except Exception as e:
    st.error(f"Database error: {e}")
```

## Common Patterns

```python
# Select all
resp = client.table("retailers").select("*").order("retailer_name").execute()

# Select with filter
resp = client.table("retailers").select("*").eq("zone", "North").execute()

# Select with join (foreign key)
resp = client.table("gift_selections").select("*, gifts_catalog(*)").execute()

# Single record
resp = client.table("retailers").select("*").eq("sf_id", sf_id).limit(1).execute()

# Upsert (idempotent insert/update)
resp = client.table("retailers").upsert(record, on_conflict="sf_id").execute()

# Call RPC function
resp = client.rpc("replace_selections", {"p_retailer": sf_id, "p_selections": json_str, "p_user": name}).execute()
```

## Demo Mode Pattern

```python
_DEMO_MODE = not os.environ.get("SUPABASE_URL")

def get_data():
    if _DEMO_MODE:
        return _DEMO_DATA  # in-memory fallback
    return client.table("data").select("*").execute().data
```

## Don'ts

- NEVER expose service key in client-side code or git
- NEVER skip error checking on responses
- NEVER use string interpolation in queries — use .eq(), .in_() etc.
- NEVER hardcode demo data outside db.py
