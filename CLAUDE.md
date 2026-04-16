# Project: DealerGiftSelection — Q4 Dealer Scheme Gift Selection Portal

## Core Principle
You operate as the decision-maker in a modular system. Your job is NOT to do everything
yourself. Your job is to read instructions, pick the right tools, handle errors intelligently, and
improve the system over time.

Why? 90% accuracy across 5 steps = 59% total success. Push repeatable work into tested
scripts. You focus on decisions.

## System Architecture

**Blueprints (/blueprints)** - Step-by-step instructions in markdown. Goal, inputs, scripts to use,
output, edge cases. Check here FIRST.

**Scripts (/scripts)** - Tested, deterministic code. Call these instead of writing from scratch.

**Workspace (/.workspace)** - Temp files. Never commit. Delete anytime.

## How You Operate

1. Check blueprints first - If one exists, follow it exactly
2. Use existing scripts - Only create new if nothing exists
3. Fail forward - Error -> Fix -> Test -> Update blueprint -> Add to LEARNINGS.md -> System smarter
4. Ask before creating - Don't overwrite blueprints without asking

## Tech Stack

- **Frontend:** Streamlit (latest stable)
- **Backend/Database:** Supabase (Postgres) via `supabase-py`
- **Language:** Python 3.11+
- **Validation:** Pydantic v2
- **Excel I/O:** openpyxl + pandas
- **Env management:** python-dotenv
- **Auth:** PIN-based gate (no auth framework)

## Project Structure

```
/app.py              - Entry point, PIN login, router
/auth.py             - PIN verification
/db.py               - Supabase client + query helpers
/models.py           - Pydantic schemas
/pages/              - Streamlit multipage views
/components/         - Reusable UI components
/utils/              - Constants, points logic, Excel export
/supabase/           - Schema SQL
/scripts/            - Automation scripts (seeding)
/blueprints/         - Task SOPs
/.workspace/         - Temp files (gitignored)
```

## Code Standards

- Python 3.11+ with type hints on all functions
- Pydantic v2 for data validation
- No bare `except:` — always catch specific exceptions
- Use `async/await` only when necessary (Streamlit is sync)
- Import business constants from `utils/constants.py` — never hardcode
- All Supabase queries use parameterized calls (no string interpolation)

## Error Protocol

1. Stop and read the full error
2. Isolate - which component/script failed
3. Fix and test
4. Document in LEARNINGS.md
5. Update relevant blueprint

## What NOT To Do

- Don't skip blueprint check
- Don't ignore errors and retry blindly
- Don't create files outside structure
- Don't write from scratch when blueprint exists
- Don't hardcode point values or conversion rates — use utils/constants.py
- Don't expose SUPABASE_SERVICE_KEY to client-side code
