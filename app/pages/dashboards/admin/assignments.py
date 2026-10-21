import logging

import streamlit as st
from pymongo.errors import PyMongoError

from db.assignments import (
    delete_class_assignment,
    list_assignments_for_class,
    update_class_assignment,
)

logger = logging.getLogger(__name__)


def render_class_assignments(class_id):
    user = st.session_state.get("user") or {}
    if user.get("permissions") != "admin":
        st.error("You must be an admin to manage class assignments.")
        return
    st.subheader("Class assignments")
    if message := st.session_state.pop("admin_assignment_success", None):
        st.success(message)
    try:
        assignments = list_assignments_for_class(class_id)
    except (ValueError, RuntimeError, PyMongoError):
        logger.exception("Failed to load class assignments")
        st.error("Could not load assignments. Try again.")
        return
    if not assignments:
        st.info("No assignments in this class yet.")
        return
    for assignment in assignments:
        assignment_id = assignment["_id"]
        key = f"admin_assignment_{class_id}_{assignment_id}"
        with st.expander(assignment.get("title", "Untitled assignment")):
            st.caption(f"{assignment.get('status', 'draft').capitalize()} · {len(assignment.get('problems', []))} problems")
            with st.form(f"{key}_edit"):
                title = st.text_input("Title", value=assignment.get("title", ""))
                description = st.text_area("Description", value=assignment.get("description", ""))
                posted = st.date_input("Posted date", value=assignment.get("posted"))
                due_date = st.date_input("Due date", value=assignment.get("due_date"))
                statuses = ["draft", "published", "closed"]
                current_status = assignment.get("status", "draft")
                status = st.selectbox("Status", statuses, index=statuses.index(current_status) if current_status in statuses else 0)
                save = st.form_submit_button("Save assignment")
            for number, problem in enumerate(assignment.get("problems", []), 1):
                st.write(f"Problem {number}")
                st.write(problem.get("content", ""))
            confirmed = st.checkbox(
                "Confirm permanent deletion of this assignment and its problems",
                key=f"{key}_confirm",
            )
            delete = st.button("Delete assignment", key=f"{key}_delete", disabled=not confirmed)
            if not save and not delete:
                continue
            try:
                if delete:
                    changed = delete_class_assignment(assignment_id, class_id, user.get("id"))
                    message = "Assignment deleted."
                else:
                    changed = update_class_assignment(
                        assignment_id, class_id, user.get("id"), title, description, status,
                        posted=posted, due_date=due_date,
                    )
                    message = "Assignment updated."
            except (ValueError, RuntimeError, PyMongoError) as error:
                logger.exception("Failed to manage class assignment")
                st.error(str(error) if isinstance(error, ValueError) else "Could not update the assignment. Try again.")
            else:
                if changed:
                    st.session_state.admin_assignment_success = message
                    st.rerun()
                else:
                    st.warning("Assignment no longer exists in this class. Refresh to reload assignments.")
