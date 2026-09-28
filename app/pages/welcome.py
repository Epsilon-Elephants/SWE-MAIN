import streamlit as st
from auth.auth import log_out_user

def welcomePage():
    first_name = st.session_state.user.get("first_name")
    st.title(body=f"Welcome {first_name}", text_alignment="center")
    st.button(on_click=log_out_user, type="primary", label="Log Out")