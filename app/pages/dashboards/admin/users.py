import logging

import streamlit as st
from pymongo.errors import PyMongoError

from db.DataBase import db

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

    st.button(
        "Back to admin dashboard",
        key="return_to_admin_dashboard",
        on_click=_return_to_admin_dashboard,
    )

    st.title("Users")
    if message := st.session_state.pop("admin_users_success", None):
        st.success(message)
    search = st.text_input("Search by name or email", max_chars=100).strip()
    sort_column, order_column, size_column = st.columns(3)
    sort_label = sort_column.selectbox("Sort by", list(SORT_FIELDS))
    order = order_column.selectbox("Order", ["Ascending", "Descending"])
    page_size = size_column.selectbox("Users per page", [25, 50, 100])

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
        st.html("""
            <style>
            .st-key-admin_users_table {
                gap: 0;
                border: 1px solid #606060;
                border-radius: 0.5rem;
                overflow: hidden;
                background: #111111;
                color: #f5f5f5;
            }
            .st-key-admin_users_table [data-testid="stVerticalBlock"] { gap: 0; }
            .st-key-admin_users_table [class*="st-key-admin_user_row_"] {
                border-top: 1px solid #404040;
                background: #111111;
            }
            .st-key-admin_users_table [class*="st-key-admin_user_row_odd_"] {
                background: #282828;
            }
            .st-key-admin_users_table [data-testid="stHorizontalBlock"] {
                align-items: center;
                min-height: 3.5rem;
                padding: 0.5rem 0.75rem;
            }
            .st-key-admin_users_table [data-testid="stMarkdownContainer"] p {
                margin: 0;
            }
            .st-key-admin_users_table [data-testid="stForm"] {
                border: 0;
                padding: 0.5rem 0.75rem;
            }
            .st-key-admin_users_table [data-testid="stButton"] button {
                min-width: 2.75rem;
                min-height: 2.5rem;
                color: #f5f5f5;
            }
            .st-key-admin_users_table [data-testid="stButton"] button p {
                font-size: 1.5rem;
            }
            </style>
        """)
        with st.container(key="admin_users_table", gap=None):
            heading = st.columns([0.5, 2, 3, 1.5], gap="small")
            for column, label in zip(heading, ["", "Name", "Email", "Permissions"]):
                column.write(label)
            for index, user in enumerate(users):
                stripe = "odd" if index % 2 else "even"
                with st.container(key=f"admin_user_row_{stripe}_{index}", gap=None):
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
