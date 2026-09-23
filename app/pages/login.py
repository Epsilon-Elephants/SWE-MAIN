import streamlit as st
from auth.auth import authenticate_user, register_user

#Login user using the authorization found in /auth/auth
# User persistence token will be st.session.state.user if validated
# We will use that same method to carry user info between pages
def login_page():
    st.title("Welcome")
    login_tab, register_tab = st.tabs(["Log in", "Register"])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Log in", type="primary")

        if submitted:
            user = authenticate_user(email, password)
            if user is None:
                st.error("Invalid email or password.")
            else:
                st.session_state.user = user
                st.rerun()

    with register_tab:
        with st.form("register_form"):
            first_name = st.text_input("First name", key="register_first_name")
            last_name = st.text_input("Last name", key="register_last_name")
            email = st.text_input("Email", key="register_email")
            password = st.text_input(
                "Password",
                type="password",
                key="register_password",
                help="Use at least 8 characters.",
            )
            confirmation = st.text_input(
                "Confirm password",
                type="password",
                key="register_confirmation",
            )
            submitted = st.form_submit_button("Create account", type="primary")

        if submitted:
            if password != confirmation:
                st.error("Passwords do not match.")
            else:
                created, message = register_user(email, password, first_name, last_name)
                if created:
                    st.success(message)
                else:
                    st.error(message)
