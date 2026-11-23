import streamlit as st

from components.feedback_ui import render_feedback_inbox
from pages.access import require_role

user = require_role("professor")
st.title("Feedback")
st.caption("Reports from students in your courses. Notes you add are private.")
render_feedback_inbox(user["id"])
