import streamlit as st
from pymongo.errors import PyMongoError

from components.problem_editor import problem_editor
from db.DataBase import db
from db.assignments import create_assignment, list_assignments_for_professor
from pages.assignment_editor import show_assignment_editor
from pages.dashboards.dashboard import Dashboard
from pages.dashboards.professor_classes import render_professor_classes
from pages.dashboards.admin.components import render_admin_header
from pages.dashboards.admin.admin import _load_admin_css
from pages.settings import SETTINGS_PAGE, load_settings_page


@st.dialog("Create assignment")
def _show_create_assignment_dialog(professor_id):
    try:
        classes = list(db.find("classes", {
            "instructor_id": db._object_id(professor_id, "professor ID"),
            "status": {"$nin": ["closed", "archived", "completed", "inactive", "cancelled"]},
            "active": {"$ne": False},
        }))
    except (ValueError, RuntimeError, PyMongoError):
        st.error("Could not load your classes. Try again.")
        return
    if not classes:
        st.info("You need an active class before creating an assignment.")
        return
    class_names = {str(classroom["_id"]): classroom["name"] for classroom in classes}
    with st.form("create_assignment_form"):
        class_id = st.selectbox("Class", options=list(class_names), format_func=class_names.get)
        title = st.text_input("Assignment title")
        description = st.text_area("Description")
        posted = st.date_input("Posted date", help="Students can see this assignment starting on this date (UTC).")
        due_date = st.date_input("Due date", help="Students can still complete the assignment after this date.")
        first_problem = problem_editor("First problem (required)", key="create_assignment_first_problem")
        submitted = st.form_submit_button("Create assignment")

    if submitted:
        try:
            if not title.strip():
                raise ValueError("Assignment title is required.")
            if posted is None or due_date is None:
                raise ValueError("Posted date and due date are required.")
            if due_date < posted:
                raise ValueError("Due date cannot be before the posted date.")
            if not first_problem.strip():
                raise ValueError("At least one problem is required.")
            create_assignment(
                title, professor_id, description, class_id=class_id,
                posted=posted, due_date=due_date, status="published",
                problems=[first_problem],
            )
        except (ValueError, RuntimeError, PyMongoError) as error:
            st.error(str(error))
        else:
            st.session_state.professor_assignment_success = "Assignment created."
            st.rerun()


def _render_assignment_card(assignment):
    assignment_id = assignment["_id"]
    with st.container(border=True, key=f"assignment_card_{assignment_id}"):
        st.markdown(f"**{assignment.get('title', 'Untitled')}**")
        st.caption(assignment.get("status", "draft").capitalize())
        if description := assignment.get("description"):
            st.write(description)
        if st.button("Open", key=f"open_{assignment_id}"):
            st.session_state.selected_assignment_id = assignment_id
            st.session_state.pop("professor_enrollment_class", None)
            st.rerun()


class professorDash(Dashboard):
    def __init__(self):
        super().__init__()

    def load_dash(self):
        st.html(_load_admin_css())
        if st.session_state.get("professor_page") == SETTINGS_PAGE:
            load_settings_page()
            return

        render_admin_header(
            "Professor dashboard",
            f"Welcome back, {st.session_state.user.get('first_name') or 'Professor'}",
        )

        # temporary interface for creating assignments and navigation to assignment editor
        professor_id = st.session_state.user.get("id")
        if not professor_id:
            st.error("Your professor account is missing an ID.")
            return

        assignment_id = st.session_state.get("selected_assignment_id")
        if assignment_id:
            show_assignment_editor(assignment_id, professor_id)
            return

        assignments_column, classes_column = st.columns([2, 1], gap="large")
        with assignments_column:
            st.subheader("Active assignments")
            if message := st.session_state.pop("professor_assignment_success", None):
                st.success(message)
            if st.button("Create assignment", type="primary", icon=":material/add:"):
                st.session_state.pop("professor_enrollment_class", None)
                _show_create_assignment_dialog(professor_id)

            try:
                assignments = list_assignments_for_professor(professor_id)
            except (ValueError, RuntimeError, PyMongoError) as error:
                st.error(f"Could not load assignments: {error}")
            else:
                active = [
                    assignment for assignment in assignments
                    if assignment.get("status", "draft")
                    not in {"draft", "closed", "archived", "completed", "cancelled"}
                ]
                if not active:
                    st.info("No active assignments yet.")
                for assignment in active:
                    _render_assignment_card(assignment)

                drafts = [a for a in assignments if a.get("status", "draft") == "draft"]
                if drafts:
                    with st.expander(f"Draft assignments ({len(drafts)})"):
                        for assignment in drafts:
                            _render_assignment_card(assignment)
                closed = [a for a in assignments if a not in active and a not in drafts]
                if closed:
                    with st.expander(f"Closed assignments ({len(closed)})"):
                        for assignment in closed:
                            _render_assignment_card(assignment)

        with classes_column:
            render_professor_classes(professor_id)
