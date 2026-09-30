import streamlit as st
from pages.dashboards.dashboard import Dashboard
from pages.dashboards.admin import adminDash
from pages.dashboards.professor import professorDash
from pages.dashboards.student import studentDash

dashboard_classes = {
    "admin" : adminDash,
    "professor": professorDash,
    "student": studentDash
}

def welcomePage():
    dash = load_dash()
    dash.load_dash()

def load_dash() -> Dashboard:
    return dashboard_classes[st.session_state.user.get("permissions")]()
    
    