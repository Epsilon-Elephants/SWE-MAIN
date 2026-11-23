import streamlit as st

from auth.auth import authenticate_user, register_user
from components import brand

# Login user using the authorization found in /auth/auth
# User persistence token will be st.session.state.user if validated
# We will use that same method to carry user info between pages
def login_page():
    st.space("medium")
    introduction, account = st.columns([6, 5], gap="large")
    with introduction:
        brand.hero_lockup()
        st.title("Better questions.\nDeeper understanding.")
        st.write(brand.TAGLINE)
        students, professors = st.columns(2)
        with students.container(border=True, height="stretch"):
            st.markdown("#### :material/edit_note: For students")
            st.write("Complete assignments, see tentative and confirmed scores, and get topic-based study suggestions.")
        with professors.container(border=True, height="stretch"):
            st.markdown("#### :material/co_present: For professors")
            st.write("Create course assignments, review Rocky's feedback, and confirm or adjust scores.")
        with st.expander("How it works"):
            st.markdown(
                "1. **Assignments:** open your course and submit your answers.\n"
                "2. **Rocky:** grades saved work in the background and provides tentative scores.\n"
                "3. **Professor review:** your professor confirms or adjusts the scores that count toward your grade.\n"
                "4. **Practice:** use feedback and topic recommendations to plan what to study next."
            )
        st.caption(f"{brand.APP_NAME} · {brand.INSTITUTION} · Built by {brand.TEAM}")
    with account, st.container(border=True):
        st.title("Welcome")
        st.caption("Students can register here. Professor accounts are provided by your course administrator.")
        login_tab, register_tab = st.tabs(["Log in", "Register"])

        with login_tab:
            with st.form("login_form"):
                email = st.text_input("Email", key="login_email")
                password = st.text_input("Password", type="password", key="login_password")
                submitted = st.form_submit_button("Log in", type="primary", width="stretch")

            if submitted:
                user, message = authenticate_user(email, password)
                if user is None:
                    st.error(message)
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
                submitted = st.form_submit_button("Create account", type="primary", width="stretch")

            if submitted:
                if password != confirmation:
                    st.error("Passwords do not match.")
                else:
                    created, message = register_user(email, password, first_name, last_name)
                    if created:
                        st.success(message)
                    else:
                        st.error(message)
