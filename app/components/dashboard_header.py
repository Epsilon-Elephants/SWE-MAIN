from html import escape

import streamlit as st

from pages.settings import open_settings


def render_dashboard_header(
    title,
    subtitle=None,
    back_label=None,
    back_callback=None,
    back_key="dashboard_header_back",
):
    """Render consistent dashboard navigation, page identity, and account controls."""
    back_column, title_column, menu_column = st.columns(
        [2, 5, 2], vertical_alignment="center",
    )
    if back_label and back_callback:
        back_column.button(
            f"← {back_label}",
            key=back_key,
            on_click=back_callback,
            type="tertiary",
            width="stretch",
        )

    title_column.title(title, text_alignment="center")
    if subtitle:
        title_column.markdown(
            f"<p class='dashboard-page-subtitle'>{escape(subtitle)}</p>",
            unsafe_allow_html=True,
        )

    menu_column.button(
        "⚙",
        key="dashboard_settings_open",
        help="Account and settings",
        on_click=open_settings,
        args=(st.session_state.get("professor_page", "dashboard"),),
        type="tertiary",
        width="stretch",
    )
