import streamlit as st

st.set_page_config(page_title="Philosophy classroom", page_icon=":material/school:", layout="wide")
st.session_state.setdefault("user", None)
user = st.session_state.user or {}
role = user.get("permissions")
if role in {"student", "professor"}:
    from homework.worker import start_grading_worker

    start_grading_worker()

with st.sidebar:
    st.markdown("### Philosophy classroom")
    if user:
        name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))
        st.caption((name or user.get("email", "Account")) + (f" · {role.capitalize()}" if role else ""))

# Explicit role-scoped routes also prevent legacy pages/ auto-discovery.
pages = [st.Page("app_pages/overview.py", title="Dashboard", icon=":material/dashboard:", default=True)]
if role in {"professor", "student"}:
    pages.extend([
        st.Page("app_pages/classes.py", title="Courses", icon=":material/school:"),
        st.Page("app_pages/course.py", title="Course", visibility="hidden"),
    ])
if role == "professor":
    pages.extend([
        st.Page("app_pages/assignments.py", title="Assignments", icon=":material/assignment:"),
        st.Page("app_pages/create_assignment.py", title="Create assignment", visibility="hidden"),
        st.Page("app_pages/edit_assignment.py", title="Assignment editor", icon=":material/edit_note:", visibility="hidden"),
    ])
if role == "student":
    pages.extend([
        st.Page("app_pages/homework.py", title="Assignments", icon=":material/assignment:"),
        st.Page("app_pages/homework_assignment.py", title="Take assignment", icon=":material/edit_note:", visibility="hidden"),
        st.Page("app_pages/practice.py", title="Practice", icon=":material/psychology:"),
    ])
if role in {"student", "professor"}:
    pages.append(st.Page("app_pages/settings.py", title="Account", icon=":material/settings:"))
    if st.sidebar.button("Log out", icon=":material/logout:", key="account_logout"):
        st.session_state.clear()
        st.rerun()
st.navigation(pages, position="sidebar" if user else "hidden").run()
