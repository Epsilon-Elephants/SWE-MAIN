import streamlit as st

from courses.views import show_courses

user = st.session_state.get("user") or {}
if user.get("permissions") not in {"professor", "student"} or not user.get("id"):
    st.error("Sign in to view your courses.")
    st.stop()
show_courses(user)
