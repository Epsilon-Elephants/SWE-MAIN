import streamlit as st
from components import brand
from components.feedback_ui import feedback_dialog
from components.notifications import show_notices

st.session_state.setdefault("user", None)
brand.page_config(signed_in=bool(st.session_state.user))
brand.inject_styles()
show_notices()
user = st.session_state.user or {}
role = user.get("permissions")
if role in {"student", "professor"}:
    from homework.worker import start_grading_worker

    start_grading_worker()

# Signed-out visitors see only the login page, so leave the sidebar empty (and hidden).
if user:
    brand.render_logo()
    with st.sidebar:
        name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))
        brand.sidebar_identity(name or user.get("email", "Account"), role)

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
        st.Page("app_pages/feedback_inbox.py", title="Feedback", icon=":material/feedback:"),
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
page = st.navigation(pages, position="sidebar" if user else "hidden")
if role in {"student", "professor"}:
    if st.sidebar.button("Report an issue", icon=":material/flag:", key="report_issue", width="stretch"):
        feedback_dialog(page.title)
    if st.sidebar.button("Log out", icon=":material/logout:", key="account_logout", width="stretch"):
        st.session_state.clear()
        st.rerun()
    with st.sidebar:
        brand.sidebar_footer()
page.run()
