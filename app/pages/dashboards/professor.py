import streamlit as st

from app.pages.dashboards.dashboard import Dashboard

class professorDash(Dashboard):
    def __init__(self):
        super().__init__()
    def load_dash(self):
        super().load_dash()