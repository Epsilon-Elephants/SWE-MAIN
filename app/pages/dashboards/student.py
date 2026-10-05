import os

import streamlit as st

from app.pages.dashboards.dashboard import Dashboard
from app.rocky.rocky import rocky

class studentDash(Dashboard):
    def __init__(self):
        super().__init__()
    def load_dash(self):
        super().load_dash()
