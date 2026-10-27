import streamlit as st

st.set_page_config(page_title="Philosophy classroom", page_icon=":material/school:", layout="wide")
st.session_state.setdefault("user", None)
user = st.session_state.user or {}
role = user.get("permissions")

with st.sidebar:
    st.caption("TEACHING & LEARNING")
    st.title("Philosophy classroom")
    if user:
        st.caption(" ".join(filter(None, [user.get("first_name"), user.get("last_name")])))
        st.caption(user.get("email", ""))
        st.badge(role.capitalize() if role else "Account", icon=":material/person:")

# Explicit role-scoped routes also prevent legacy pages/ auto-discovery.
pages = [st.Page("pages/home.py", title="Overview", icon=":material/dashboard:", default=True)]
if role == "professor":
    pages.extend([
        st.Page("app_pages/classes.py", title="Classes", icon=":material/groups:"),
        st.Page("app_pages/create_assignment.py", title="Create assignment", icon=":material/add_circle:"),
        st.Page("app_pages/edit_assignment.py", title="Assignment editor", icon=":material/edit_note:", visibility="hidden"),
    ])
if role == "student":
    pages.extend([
        st.Page("pages/homework.py", title="Homework", icon=":material/assignment:"),
        st.Page("pages/homework_assignment.py", title="Take assignment", icon=":material/edit_note:", visibility="hidden"),
        st.Page("app_pages/practice.py", title="Practice", icon=":material/psychology:"),
    ])
if role in {"student", "professor"}:
    pages.append(st.Page("app_pages/settings.py", title="Account", icon=":material/settings:"))
    if st.sidebar.button("Log out", icon=":material/logout:", key="account_logout"):
        st.session_state.clear()
        st.rerun()
st.navigation(pages, position="sidebar" if user else "hidden").run()
