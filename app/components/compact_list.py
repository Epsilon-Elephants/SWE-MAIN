"""Five-item previews with a bounded, paginated popup for the remaining items."""

import streamlit as st

PAGE_SIZE = 5
OPEN_LIST = "expanded_list"


def close_compact_list():
    st.session_state.pop(OPEN_LIST, None)


def _move_page(key, offset):
    st.session_state[key] += offset


@st.dialog("See more", width="large", on_dismiss=close_compact_list)
def _list_dialog(items, render_item, title, key):
    st.subheader(title)
    page_key = f"{key}_popup_page"
    page = min(st.session_state.get(page_key, 0), (len(items) - 1) // PAGE_SIZE)
    st.session_state[page_key] = max(0, page)
    start = max(0, page) * PAGE_SIZE
    st.caption(f"Showing {start + PAGE_SIZE + 1}–{min(start + PAGE_SIZE, len(items)) + PAGE_SIZE} of {len(items) + PAGE_SIZE}")
    for item in items[start:start + PAGE_SIZE]:
        render_item(item)
    with st.container(horizontal=True):
        st.button("Previous", key=f"{key}_popup_previous", disabled=page == 0,
                  on_click=_move_page, args=(page_key, -1))
        st.button("Next", key=f"{key}_popup_next", disabled=start + PAGE_SIZE >= len(items),
                  on_click=_move_page, args=(page_key, 1))
        if st.button("Close", key=f"{key}_popup_close"):
            close_compact_list()
            st.rerun()


def compact_list(items, render_item, *, title, key, columns=1):
    """Callbacks keep their normal actions; items are rendered in just one place."""
    preview = items[:PAGE_SIZE]
    for offset in range(0, len(preview), columns):
        containers = st.columns(columns) if columns > 1 else [st.container()]
        for container, item in zip(containers, preview[offset:offset + columns]):
            with container:
                render_item(item)
    if len(items) <= PAGE_SIZE:
        if st.session_state.get(OPEN_LIST) == key:
            close_compact_list()
        return
    if st.button(f"See more ({len(items) - PAGE_SIZE})", key=f"{key}_see_more"):
        st.session_state[OPEN_LIST] = key
        st.session_state[f"{key}_popup_page"] = 0
    if st.session_state.get(OPEN_LIST) == key:
        _list_dialog(items[PAGE_SIZE:], render_item, title, key)
