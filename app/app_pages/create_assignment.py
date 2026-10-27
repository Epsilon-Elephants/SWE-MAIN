import streamlit as st

from pages.access import require_role
from pages.dashboards.professor import render_create_assignment

user = require_role("professor")
st.caption("COURSEWORK / AUTHORING")
st.title("Create assignment")
st.caption("Start with a question, then add problems and private grading criteria in the editor.")
if st.button("Back to overview", icon=":material/arrow_back:"):
    st.switch_page("pages/home.py")
render_create_assignment(user["id"])
