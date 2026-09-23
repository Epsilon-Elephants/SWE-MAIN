import streamlit as st

def welcomePage():
    first_name = st.session_state.user.get("first_name")
    st.title(body=f"Welcome {first_name}", text_alignment="center")