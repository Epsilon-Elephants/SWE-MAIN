import streamlit as st


SETTINGS_PAGE = "settings"
PAGE_SIZES = [10, 25, 50]


def open_settings(return_page=None):
    st.session_state.settings_return_page = (
        return_page or st.session_state.get("admin_page", "dashboard")
    )
    st.session_state.admin_page = SETTINGS_PAGE


def _return_from_settings():
    st.session_state.admin_page = st.session_state.pop(
        "settings_return_page", "dashboard",
    )


def _apply_page_size():
    st.session_state.admin_users_page_size = st.session_state.admin_default_page_size
    st.session_state.admin_users_page = 0
    st.session_state.admin_classes_page = 0
    st.session_state.admin_enrolled_page = 0
    st.session_state.admin_available_page = 0


def _logout():
    st.session_state.clear()


def load_settings_page():
    user = st.session_state.get("user") or {}
    if not user:
        st.error("Sign in to view settings.")
        return

    st.session_state.setdefault("admin_compact_tables", False)
    st.session_state.setdefault("admin_default_page_size", 10)

    back_column, title_column, spacer = st.columns(
        [1.2, 5, 1.2], vertical_alignment="center",
    )
    back_column.button(
        "← Back",
        key="settings_back",
        on_click=_return_from_settings,
        type="tertiary",
    )
    title_column.title("Settings", text_alignment="center")
    title_column.markdown(
        "<p class='admin-page-subtitle'>Manage your account and dashboard preferences.</p>",
        unsafe_allow_html=True,
    )
    spacer.empty()

    account_column, display_column = st.columns(2)
    with account_column.container(key="settings_account_card"):
        st.markdown("### Account")
        name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))
        st.text_input("Name", value=name or "Administrator", disabled=True)
        st.text_input("Email", value=user.get("email", ""), disabled=True)
        st.text_input("Role", value=user.get("permissions", ""), disabled=True)

    with display_column.container(key="settings_display_card"):
        st.markdown("### Display")
        st.toggle(
            "Compact tables",
            key="admin_compact_tables",
            help="Reduce table row height so more results fit on screen.",
        )
        st.selectbox(
            "Rows per page",
            PAGE_SIZES,
            key="admin_default_page_size",
            on_change=_apply_page_size,
            help="Set the default size for admin result lists.",
        )

    with st.container(key="settings_session_card"):
        session_text, logout_column = st.columns([4, 1], vertical_alignment="center")
        session_text.markdown("### Session")
        session_text.caption("Sign out of this account on the current device.")
        if logout_column.button(
            "Log out",
            key="settings_logout",
            type="primary",
            width="stretch",
        ):
            _logout()
            st.rerun()
