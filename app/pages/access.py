"""Shared role guard for registered Streamlit pages."""
import streamlit as st


def require_role(role):
    user = st.session_state.get("user") or {}
    if user.get("permissions") != role or not user.get("id"):
        st.error(f"Sign in with a {role} account to view this page.")
        st.stop()
    return user
