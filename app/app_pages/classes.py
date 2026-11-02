import streamlit as st

from pages.access import require_role
from pages.dashboards.professor_classes import render_professor_classes

user = require_role("professor")
st.caption("TEACHING / CLASS MANAGEMENT")
st.title("Your classes")
st.caption("Manage enrollment and class grades for the classes you teach.")
render_professor_classes(user["id"])
