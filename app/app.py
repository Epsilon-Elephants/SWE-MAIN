import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = Path(__file__).resolve().parent
for candidate in (str(PROJECT_ROOT), str(APP_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.pages.login import login_page
from app.pages.welcome import welcomePage

if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    login_page()
else:
    with st.sidebar:
        st.write(f"Signed in as {st.session_state.user['email']}")
        if st.button("Log out"):
            st.session_state.user = None
            st.rerun()
    welcomePage()
