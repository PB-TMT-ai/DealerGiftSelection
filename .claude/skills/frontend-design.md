# Streamlit UI Design Skill

## Layout

- Always use `st.set_page_config(layout="wide")` in the entry point
- Use `st.columns()` for side-by-side content
- Use `st.container(border=True)` for card-like sections
- Use `st.expander()` for collapsible detail panels
- Use `st.sidebar` for filters and navigation

## Typography & Display

- `st.markdown("## Heading")` for page titles
- `st.caption()` for secondary/helper text
- `st.metric()` for KPI values with labels
- `st.divider()` to separate sections

## Data Display

- `st.dataframe()` for interactive tables (sortable, searchable)
- `st.data_editor()` only when inline editing is needed
- Always set `use_container_width=True` and `hide_index=True`
- Use `st.column_config` for custom column formatting

## Forms & Input

- `st.form()` for multi-field submissions (prevents reruns on each input)
- `st.number_input()` for quantities and numeric values
- `st.selectbox()` for single-choice dropdowns
- `st.multiselect()` for multi-choice filters
- `st.text_input()` for free-text search
- `st.radio()` with `horizontal=True` for toggle options

## Feedback

- `st.toast()` for success messages
- `st.error()` for validation failures
- `st.warning()` for cautionary states
- `st.info()` for helpful context
- `st.spinner()` on every data fetch

## Don'ts

- No custom CSS unless absolutely essential
- No `st.write()` for structured content — use specific widgets
- No hidden states — use disabled states with clear reasons
- No blocking without feedback — always show spinners

## Example

```python
st.markdown("## Dashboard")

cols = st.columns(3)
with cols[0]:
    st.metric("Total", f"{total:,}")
with cols[1]:
    st.metric("Used", f"{used:,}")
with cols[2]:
    st.metric("Utilization", f"{pct:.1f}%")

st.divider()

st.dataframe(df, use_container_width=True, hide_index=True)
```
