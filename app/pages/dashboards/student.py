import streamlit as st
from pages.dashboards.dashboard import Dashboard
from rocky.rocky import rocky
import os

class studentDash(Dashboard):
    def __init__(self):
        super().__init__()
    def load_dash(self):
        super().load_dash()
