# API Integration Skill (Python)

## Supabase RPC Calls

```python
import json

def call_rpc(client, fn_name: str, params: dict):
    """Call a Supabase RPC function with error handling."""
    try:
        resp = client.rpc(fn_name, params).execute()
        return resp.data
    except Exception as e:
        raise RuntimeError(f"RPC {fn_name} failed: {e}")
```

## JSONB Parameters

```python
# When passing JSONB to Postgres RPC, serialize with json.dumps
selections = [{"gift_id": 1, "points_used": 750, "quantity": 1}]
client.rpc("replace_selections", {
    "p_retailer": "SF001",
    "p_selections": json.dumps(selections),
    "p_user": "SM North"
}).execute()
```

## Retry with Backoff

```python
import time

def fetch_with_retry(fn, retries: int = 3):
    for i in range(retries):
        try:
            return fn()
        except Exception as e:
            if i == retries - 1:
                raise
            time.sleep(2 ** i)
```

## Environment Variables

```python
from dotenv import load_dotenv
import os

load_dotenv()
url = os.environ["SUPABASE_URL"]  # Raises KeyError if missing
key = os.environ.get("SUPABASE_KEY", "")  # Empty string fallback
```

## Don'ts

- NEVER hardcode API keys or URLs
- NEVER log sensitive data (keys, PINs)
- NEVER use string concatenation for query building
- NEVER ignore errors from RPC calls — always catch and display to user
