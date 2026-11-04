import streamlit as st
from pages.access import require_role
from db.assignments import list_assignments_for_professor
from pages.dashboards.professor import _load_assignment_context, render_assignment_groups
from pymongo.errors import PyMongoError

user = require_role("professor")
st.title("Assignments")
if st.button("Create assignment", type="primary", icon=":material/add:"):
    st.switch_page("app_pages/create_assignment.py")
try:
    assignments = list_assignments_for_professor(user["id"])
    classes, summaries = _load_assignment_context(user["id"], assignments)
    render_assignment_groups(assignments, classes, summaries)
except (ValueError, RuntimeError, PyMongoError):
    st.error("Could not load your assignments. Try again.")
