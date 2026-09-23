import streamlit as st
from auth.auth import reg_usr

def loginPage():
    st.title(body="Welcome", text_alignment="center")

    st.button(label="Register", on_click=reg_usr)
    