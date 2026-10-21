import logging

import streamlit as st
from pymongo.errors import PyMongoError

from db.DataBase import db
from pages.dashboards.admin.components import render_admin_header
from pages.dashboards.admin.styles import (
    table_header_key,
    table_row_key,
    table_shell_key,
)

logger = logging.getLogger(__name__)

SORT_FIELDS = {
    "First name": "first_name",
    "Last name": "last_name",
    "Email": "email",
    "Role": "permissions",
    "Date created": "created_at",
}
USER_ROLES = ["student", "professor", "admin"]


@st.cache_resource
def _ensure_user_indexes():
    db.ensure_user_directory_indexes()


def _return_to_admin_dashboard():
    st.session_state.admin_page = "dashboard"


def load_users_page():
    if (st.session_state.get("user") or {}).get("permissions") != "admin":
        st.error("You must be an admin to view users.")
        return

    render_admin_header(
        "Users",
        "Find accounts and manage access.",
        back_label="Admin",
        back_callback=_return_to_admin_dashboard,
        back_key="return_to_admin_dashboard",
    )
    if message := st.session_state.pop("admin_users_success", None):
        st.success(message)
    search = st.text_input("Search by name or email", max_chars=100).strip()
    sort_column, order_column, size_column = st.columns(3)
    sort_label = sort_column.selectbox("Sort by", list(SORT_FIELDS))
    order = order_column.selectbox("Order", ["Ascending", "Descending"])
    page_sizes = [10, 25, 50]
    default_page_size = st.session_state.get("admin_default_page_size", 10)
    page_size = size_column.selectbox(
        "Users per page",
        page_sizes,
        index=page_sizes.index(default_page_size),
        key="admin_users_page_size",
    )

    settings = (search, sort_label, order, page_size)
    if st.session_state.get("admin_users_settings") != settings:
        st.session_state.admin_users_settings = settings
        st.session_state.admin_users_page = 0
    page = st.session_state.get("admin_users_page", 0)

    try:
        _ensure_user_indexes()
        users, has_next = db.list_users_page(
            search=search,
            sort_field=SORT_FIELDS[sort_label],
            descending=order == "Descending",
            page=page,
            page_size=page_size,
        )
    except (PyMongoError, RuntimeError):
        logger.exception("Failed to load the admin user directory")
        st.error("Could not load users. Try again, or narrow your search.")
        return

    if users:
        with st.container(key=table_shell_key("users"), gap=None):
            with st.container(key=table_header_key("users"), gap=None):
                heading = st.columns([0.5, 2, 3, 1.5], gap="small")
                for column, label in zip(heading, ["", "Name", "Email", "Permissions"]):
                    column.write(label)
            for index, user in enumerate(users):
                with st.container(key=table_row_key("users", index), gap=None):
                    email = user.get("email", "")
                    name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))
                    current_role = user.get("permissions", "")
                    row = st.columns([0.5, 2, 3, 1.5], gap="small")
                    opened = st.session_state.get("admin_users_open") == email
                    if row[0].button(
                        "▾" if opened else "▸", key=f"user_expand_{email}",
                        type="tertiary",
                    ):
                        st.session_state.admin_users_open = None if opened else email
                        st.rerun()
                    row[1].text(name or "—")
                    row[2].text(email)
                    row[3].text(current_role)
                    if opened:
                        with st.form(key=f"user_permissions_{email}"):
                            role = st.selectbox(
                                "Permission", USER_ROLES,
                                index=USER_ROLES.index(current_role) if current_role in USER_ROLES else None,
                                key=f"user_role_{email}",
                            )
                            saved = st.form_submit_button("Save")
                        if saved:
                            if role not in USER_ROLES:
                                st.error("Select a permission before saving.")
                                continue
                            try:
                                result = db.update_one("users", {"email": email}, {"permissions": role})
                            except (PyMongoError, RuntimeError):
                                logger.exception("Failed to update user permissions")
                                st.error("Could not save permissions. Try again.")
                                continue
                            if not result.matched_count:
                                st.error("This user no longer exists. Refresh the page.")
                                continue
                            session_user = st.session_state.get("user") or {}
                            if session_user.get("email") == email:
                                st.session_state.user = {**session_user, "permissions": role}
                            st.session_state.admin_users_success = f"Permissions saved for {email}."
                            st.rerun()
    else:
        st.info("No users found on this page." if page else "No users found.")

    st.caption(f"Page {page + 1} · {len(users)} users on this page")
    previous, next_page = st.columns(2)
    if previous.button("Previous", disabled=page == 0, key="admin_users_previous"):
        st.session_state.admin_users_page = page - 1
        st.rerun()
    if next_page.button("Next", disabled=not has_next, key="admin_users_next"):
        st.session_state.admin_users_page = page + 1
        st.rerun()
