from html import escape

import streamlit as st

from pages.settings import open_settings


def render_admin_header(
    title,
    subtitle=None,
    back_label=None,
    back_callback=None,
    back_key="admin_header_back",
):
    """Render consistent admin navigation, page identity, and account controls."""
    st.session_state.setdefault("admin_compact_tables", False)
    st.session_state.setdefault("admin_default_page_size", 10)

    back_column, title_column, menu_column = st.columns(
        [1.2, 5, 1.2], vertical_alignment="center",
    )
    if back_label and back_callback:
        back_column.button(
            f"← {back_label}",
            key=back_key,
            on_click=back_callback,
            type="tertiary",
        )

    title_column.title(title, text_alignment="center")
    if subtitle:
        title_column.markdown(
            f"<p class='admin-page-subtitle'>{escape(subtitle)}</p>",
            unsafe_allow_html=True,
        )

    menu_column.button(
        "⚙",
        key="admin_settings_open",
        help="Account and settings",
        on_click=open_settings,
        args=(st.session_state.get("admin_page", "dashboard"),),
        type="tertiary",
        width="stretch",
    )
