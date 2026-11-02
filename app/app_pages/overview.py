import streamlit as st

from pages.login import login_page
from pages.welcome import welcomePage

if st.session_state.user is None:
    login_page()
else:
    welcomePage()
