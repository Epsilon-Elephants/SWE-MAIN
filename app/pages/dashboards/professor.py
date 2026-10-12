import streamlit as st
from pymongo.errors import PyMongoError

from db.assignments import create_assignment, list_assignments_for_professor
from pages.assignment_editor import show_assignment_editor
from pages.dashboards.dashboard import Dashboard


class professorDash(Dashboard):
    def __init__(self):
        super().__init__()

    def load_dash(self):
        super().load_dash()

        # temporary interface for creating assignments and navigation to assignment editor
        professor_id = st.session_state.user.get("id")
        if not professor_id:
            st.error("Your professor account is missing an ID.")
            return

        assignment_id = st.session_state.get("selected_assignment_id")
        if assignment_id:
            show_assignment_editor(assignment_id, professor_id)
            return

        st.subheader("Assignments")

        with st.form("create_assignment_form", clear_on_submit=True):
            title = st.text_input("Assignment title")
            description = st.text_area("Description")
            submitted = st.form_submit_button("Create assignment")

        if submitted:
            try:
                create_assignment(title, professor_id, description)
                st.success("Assignment created.")
            except (ValueError, RuntimeError, PyMongoError) as error:
                st.error(str(error))

        try:
            assignments = list_assignments_for_professor(professor_id)
        except (ValueError, RuntimeError, PyMongoError) as error:
            st.error(f"Could not load assignments: {error}")
            return

        if not assignments:
            st.info("No assignments yet.")
            return

        for assignment in assignments:
            assignment_id = assignment["_id"]
            title_column, button_column = st.columns([4, 1])
            title_column.write(
                f"**{assignment.get('title', 'Untitled')}** "
                f"({assignment.get('status', 'draft')})"
            )
            if button_column.button("Open", key=f"open_{assignment_id}"):
                st.session_state.selected_assignment_id = assignment_id
                st.rerun()
