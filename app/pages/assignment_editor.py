import logging

import streamlit as st
from pymongo.errors import PyMongoError

from components.problem_editor import problem_editor
from db.assignments import (
    add_problem,
    delete_assignment,
    delete_problem,
    get_assignment,
    set_assignment_status,
    update_assignment,
    update_problem,
)
from db.completed_assignments import list_submissions_for_assignment

logger = logging.getLogger(__name__)


def _student_name(user):
    user = user or {}
    name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))
    return name or "Unknown student"


def _format_timestamp(value):
    return value.strftime("%b %d, %Y %H:%M UTC") if hasattr(value, "strftime") else ""


def _render_submissions(assignment_id):
    st.markdown("**Submissions**")
    try:
        rows = list_submissions_for_assignment(assignment_id)
    except (ValueError, RuntimeError, PyMongoError):
        logger.exception("Failed to load submissions")
        st.error("Could not load submissions. Try again.")
        return
    if not rows:
        st.info("No submissions yet.")
        return
    st.caption(f"{len(rows)} student{'s' if len(rows) != 1 else ''} submitted.")
    st.dataframe(
        [
            {
                "Student": _student_name(row.get("user")),
                "Email": (row.get("user") or {}).get("email", ""),
                "Best score": row.get("best_score"),
                "Latest score": row.get("latest_score"),
                "Attempts": row.get("attempts", 0),
                "Last submitted": _format_timestamp(row.get("last_completed")),
            }
            for row in rows
        ],
        hide_index=True,
        width="stretch",
    )


def show_assignment_editor(assignment_id, professor_id: str):
    if st.button("Back to assignments", key="back_to_assignments"):
        st.session_state.pop("selected_assignment_id", None)
        st.rerun()

    try:
        assignment = get_assignment(assignment_id)
    except (ValueError, RuntimeError, PyMongoError) as error:
        st.error(str(error))
        return

    if not assignment or assignment.get("professor_id") != professor_id:
        st.error("Assignment not found.")
        return

    assignment_key = str(assignment_id)
    current_status = assignment.get("status", "draft")
    st.subheader("Assignment editor")
    st.caption(f"Status: {current_status.capitalize()}")

    with st.form(f"assignment_{assignment_key}"):
        title = st.text_input("Title", value=assignment.get("title", ""))
        description = st.text_area(
            "Description", value=assignment.get("description", "")
        )
        posted = st.date_input(
            "Posted date", value=assignment.get("posted") or "today",
            help="Students can see this assignment starting on this date (UTC).",
        )
        due_date = st.date_input(
            "Due date", value=assignment.get("due_date"),
            help="Students can still complete the assignment after this date.",
        )
        save_assignment = st.form_submit_button("Save assignment")

    if save_assignment:
        try:
            if not title.strip():
                raise ValueError("Assignment title is required.")
            if posted is None or due_date is None:
                raise ValueError("Posted date and due date are required.")
            if due_date < posted:
                raise ValueError("Due date cannot be before the posted date.")
            if not assignment.get("problems"):
                raise ValueError("At least one problem is required. Add a problem before saving.")
            update_assignment(
                assignment_id,
                professor_id,
                title,
                description,
                # Saving publishes drafts but must not silently reopen a closed assignment.
                "closed" if current_status == "closed" else "published",
                posted=posted,
                due_date=due_date,
            )
            st.rerun()
        except (ValueError, RuntimeError, PyMongoError) as error:
            st.error(str(error))

    if current_status == "published":
        status_label, new_status = "Close assignment", "closed"
    elif current_status == "closed":
        status_label, new_status = "Reopen assignment", "published"
    else:
        status_label = new_status = None
    if status_label and st.button(status_label, key=f"status_{assignment_key}"):
        try:
            set_assignment_status(assignment_id, professor_id, new_status)
        except (ValueError, RuntimeError, PyMongoError) as error:
            st.error(str(error))
        else:
            st.rerun()

    confirm_delete = st.checkbox("Confirm assignment deletion")
    if st.button("Delete assignment", disabled=not confirm_delete):
        try:
            if delete_assignment(assignment_id, professor_id):
                st.session_state.pop("selected_assignment_id", None)
                st.rerun()
        except (ValueError, RuntimeError, PyMongoError) as error:
            st.error(str(error))

    st.divider()
    st.markdown("**Problems**")

    for number, problem in enumerate(assignment.get("problems", []), start=1):
        problem_id = problem.get("problem_id")
        if not problem_id:
            continue

        with st.form(f"problem_{assignment_key}_{problem_id}"):
            content = problem_editor(
                f"Problem {number}",
                key=f"content_{assignment_key}_{problem_id}",
                initial_content=problem.get("content", ""),
            )
            save_problem = st.form_submit_button("Save problem")
            remove_problem = st.form_submit_button(
                "Remove problem", disabled=len(assignment.get("problems", [])) <= 1,
            )

        try:
            if save_problem:
                update_problem(
                    assignment_id,
                    professor_id,
                    problem_id,
                    content,
                )
                st.rerun()
            if remove_problem:
                delete_problem(assignment_id, professor_id, problem_id)
                st.rerun()
        except (ValueError, RuntimeError, PyMongoError) as error:
            st.error(str(error))

    with st.form(f"new_problem_{assignment_key}", clear_on_submit=True):
        new_content = problem_editor(
            "New problem",
            key=f"new_content_{assignment_key}",
        )
        add_submitted = st.form_submit_button("Add problem")

    if add_submitted:
        try:
            add_problem(assignment_id, professor_id, new_content)
            st.rerun()
        except (ValueError, RuntimeError, PyMongoError) as error:
            st.error(str(error))

    st.divider()
    _render_submissions(assignment_id)
