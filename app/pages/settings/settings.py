import streamlit as st


SETTINGS_PAGE = "settings"


def open_settings(return_page=None):
    st.switch_page("app_pages/settings.py")


def _return_from_settings():
    st.switch_page("app_pages/overview.py")


def load_settings_page():
    user = st.session_state.get("user") or {}
    if not user:
        st.error("Sign in to view settings.")
        return

    back_column, title_column, spacer = st.columns(
        [2, 5, 2], vertical_alignment="center",
    )
    if back_column.button(
        "← Back",
        key="settings_back",
        type="tertiary",
        width="stretch",
    ):
        _return_from_settings()
    title_column.title("Settings")
    title_column.caption("Manage your account and appearance.")
    spacer.empty()

    account_column = st.container()
    with account_column.container(key="settings_account_card", border=True):
        st.markdown("### Account")
        name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))
        st.text_input("Name", value=name or user.get("permissions", "Account").capitalize(), disabled=True)
        st.text_input("Email", value=user.get("email", ""), disabled=True)
        st.text_input("Role", value=user.get("permissions", ""), disabled=True)

    with st.container(border=True):
        st.markdown("### Appearance")
        st.write("Choose Light, Dark, or Use system setting from the theme selector in the app's top-right settings menu.")
    st.caption("Use Log out in the sidebar to end your session.")
