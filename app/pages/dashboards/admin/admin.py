import streamlit as st

from pages.dashboards.admin.classes import load_classes_page
from pages.dashboards.admin.users import load_users_page
from pages.dashboards.dashboard import Dashboard


ADMIN_HOME = "dashboard"
USERS_PAGE = "users"
CLASSES_PAGE = "classes"


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

        if st.session_state.admin_page == USERS_PAGE:
            load_users_page()
            return
        if st.session_state.admin_page == CLASSES_PAGE:
            load_classes_page()
            return

        super().load_dash()
        st.markdown(
            "<p style='text-align:center'>Choose an admin tool.</p>",
            unsafe_allow_html=True,
        )
        _, actions, _ = st.columns([1, 2, 1])
        actions.button(
            "View all users",
            type="primary",
            key="open_admin_users",
            on_click=_open_users_page,
            width="stretch",
        )
        actions.button(
            "Manage classes",
            type="primary",
            key="open_admin_classes",
            on_click=_open_classes_page,
            width="stretch",
        )
