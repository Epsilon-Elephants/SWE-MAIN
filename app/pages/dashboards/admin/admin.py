import streamlit as st

from pages.dashboards.admin.users import load_users_page
from pages.dashboards.dashboard import Dashboard


ADMIN_HOME = "dashboard"
USERS_PAGE = "users"


def _open_users_page():
    st.session_state.admin_page = USERS_PAGE


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

        super().load_dash()
        st.write("Manage users and browse registered accounts.")
        st.button(
            "View all users",
            type="primary",
            key="open_admin_users",
            on_click=_open_users_page,
        )
