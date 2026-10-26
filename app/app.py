from pathlib import Path

import streamlit as st

st.set_page_config(layout="wide")
st.session_state.setdefault("user", None)
st.html(Path(__file__).with_name("styles").joinpath("app.css"))

if st.session_state.user and st.session_state.user.get("permissions") != "professor":
    account, logout = st.columns([5, 1], vertical_alignment="center")
    account.caption(f"Signed in as {st.session_state.user['email']}")
    if logout.button("Log out"):
        st.session_state.clear()
        st.session_state.user = None
        st.rerun()

# Explicit, role-scoped navigation disables automatic discovery of pages/.
pages = [st.Page("pages/home.py", title="Home", default=True)]
if (st.session_state.user or {}).get("permissions") == "student":
    pages.extend([
        st.Page("pages/homework.py", title="Homework", icon=":material/assignment:"),
        st.Page("pages/homework_assignment.py", title="Assignment", icon=":material/edit_note:"),
    ])
st.navigation(pages, position="hidden").run()
