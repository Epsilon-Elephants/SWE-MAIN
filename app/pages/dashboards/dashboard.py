import streamlit as st
from abc import abstractmethod

class Dashboard:
    def __init__(self):
        pass
    def load_dash(self):
        st.title(body=f"Hello {st.session_state.user.get("first_name")}", text_alignment="center")