import streamlit as st

from pages.dashboards.dashboard import Dashboard
from pages.dashboards.professor import professorDash
from pages.dashboards.student.student import studentDash

dashboard_classes = {
    "professor": professorDash,
    "student": studentDash
}

def welcomePage():
    dash = load_dash()
    if dash is not None:
        dash.load_dash()

def load_dash() -> Dashboard | None:
    dashboard = dashboard_classes.get(st.session_state.user.get("permissions"))
    if dashboard is None:
        st.error("Your account does not have a supported role.")
        return None
    return dashboard()
