import streamlit as st

from pages.dashboards.dashboard import Dashboard

class professorDash(Dashboard):
    def __init__(self):
        super().__init__()
    def load_dash(self):
        st.title(body="Prof")
        super().load_dash()