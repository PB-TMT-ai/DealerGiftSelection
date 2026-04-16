# Project Learnings

Track errors, solutions, and insights. System gets smarter with each entry.

## Format

Date | Component | Issue | Resolution | Insight

---

## Entries

(Add new entries at top)

2026-04-16 | db.py | Streamlit Cloud can't reach localhost Supabase | Added demo mode with in-memory data when SUPABASE_URL is unset | Always provide an offline fallback for frontend testing
2026-04-16 | .gitignore | __pycache__ files were being tracked | Added `__pycache__/` and `*.py[cod]` patterns | Python cache dirs need explicit gitignore entries
2026-04-16 | pip install | PyJWT conflict with system package on Linux | Used `pip install --ignore-installed PyJWT` | Debian-managed Python packages can block pip installs
