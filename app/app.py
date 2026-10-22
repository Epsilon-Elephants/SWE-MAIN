import streamlit as st
from pathlib import Path

st.set_page_config(layout="wide")

from pages.login import login_page
from pages.welcome import welcomePage

st.session_state.setdefault("user", None)


def render_app():
    st.html(Path(__file__).with_name("styles").joinpath("app.css"))
    if st.session_state.user is None:
        login_page()
    else:
        if st.session_state.user.get("permissions") != "professor":
            account, logout = st.columns([5, 1], vertical_alignment="center")
            account.caption(f"Signed in as {st.session_state.user['email']}")
            if logout.button("Log out"):
                st.session_state.user = None
                st.rerun()
        welcomePage()


# Explicit navigation disables automatic discovery of the pages/ directory.
st.navigation([st.Page(render_app, title="Home", default=True)], position="hidden").run()
