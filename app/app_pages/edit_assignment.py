import streamlit as st

from pages.access import require_role
from pages.assignment_editor import show_assignment_editor

user = require_role("professor")
st.caption("COURSEWORK / EDITOR")
st.title("Assignment workspace")
assignment_id = st.session_state.get("selected_assignment_id")
if assignment_id:
    show_assignment_editor(assignment_id, user["id"])
else:
    st.info("Open an assignment from Overview to edit its details and questions.")
    if st.button("Go to overview"):
        st.switch_page("pages/home.py")
