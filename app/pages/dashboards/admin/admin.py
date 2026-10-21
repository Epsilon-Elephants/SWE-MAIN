import streamlit as st
from pathlib import Path

from pages.dashboards.admin.classes import load_classes_page
from pages.dashboards.admin.components import render_admin_header
from pages.dashboards.admin.styles import load_table_styles
from pages.dashboards.admin.users import load_users_page
from pages.dashboards.dashboard import Dashboard
from pages.settings import SETTINGS_PAGE, load_settings_page


ADMIN_HOME = "dashboard"
USERS_PAGE = "users"
CLASSES_PAGE = "classes"
ADMIN_CSS_PATH = Path(__file__).resolve().parent / "admin.css"


def _load_admin_css():
    return f"<style>{ADMIN_CSS_PATH.read_text(encoding='utf-8')}</style>"


def _open_users_page():
    st.session_state.admin_page = USERS_PAGE


def _open_classes_page():
    st.session_state.admin_page = CLASSES_PAGE


class adminDash(Dashboard):
    def load_dash(self):
        user = st.session_state.get("user") or {}
        if user.get("permissions") != "admin":
            st.error("You must be an admin to view this dashboard.")
            return

        st.session_state.setdefault("admin_page", ADMIN_HOME)
        st.session_state.setdefault("admin_compact_tables", False)
        st.session_state.setdefault("admin_default_page_size", 10)
        st.html(_load_admin_css())
        st.html(load_table_styles(st.session_state.admin_compact_tables))

        if st.session_state.admin_page == SETTINGS_PAGE:
            load_settings_page()
            return
        if st.session_state.admin_page == USERS_PAGE:
            load_users_page()
            return
        if st.session_state.admin_page == CLASSES_PAGE:
            load_classes_page()
            return

        render_admin_header(
            "Admin dashboard",
            f"Welcome back, {user.get('first_name') or 'Administrator'}",
        )
        _, actions, _ = st.columns([0.5, 3, 0.5])
        users_column, classes_column = actions.columns(2)
        with users_column.container(key="admin_users_card"):
            st.markdown("### Users")
            st.caption("Search accounts and manage permissions.")
            st.button(
                "View all users",
                type="primary",
                key="open_admin_users",
                on_click=_open_users_page,
                width="stretch",
            )
        with classes_column.container(key="admin_classes_card"):
            st.markdown("### Classes")
            st.caption("Create classes, manage rosters, and update grades.")
            st.button(
                "Manage classes",
                type="primary",
                key="open_admin_classes",
                on_click=_open_classes_page,
                width="stretch",
            )
