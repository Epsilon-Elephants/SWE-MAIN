import streamlit as st


SETTINGS_PAGE = "settings"


def open_settings(return_page=None):
    page_key = "professor_page"
    st.session_state.settings_return_page = (
        return_page or st.session_state.get(page_key, "dashboard")
    )
    st.session_state[page_key] = SETTINGS_PAGE


def _return_from_settings():
    st.session_state["professor_page"] = st.session_state.pop(
        "settings_return_page", "dashboard",
    )


def _logout():
    st.session_state.clear()


def load_settings_page():
    user = st.session_state.get("user") or {}
    if not user:
        st.error("Sign in to view settings.")
        return

    back_column, title_column, spacer = st.columns(
        [2, 5, 2], vertical_alignment="center",
    )
    back_column.button(
        "← Back",
        key="settings_back",
        on_click=_return_from_settings,
        type="tertiary",
        width="stretch",
    )
    title_column.title("Settings", text_alignment="center")
    title_column.markdown(
        "<p class='dashboard-page-subtitle'>Manage your account and session.</p>",
        unsafe_allow_html=True,
    )
    spacer.empty()

    account_column = st.container()
    with account_column.container(key="settings_account_card"):
        st.markdown("### Account")
        name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))
        st.text_input("Name", value=name or user.get("permissions", "Account").capitalize(), disabled=True)
        st.text_input("Email", value=user.get("email", ""), disabled=True)
        st.text_input("Role", value=user.get("permissions", ""), disabled=True)

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
