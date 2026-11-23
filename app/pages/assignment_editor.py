import logging

import streamlit as st
from components.course_cards import status_color
from pymongo.errors import PyMongoError

from components.problem_manager import problem_manager
from db.assignments import (
    add_problem,
    delete_assignment,
    delete_problem,
    get_assignment,
    set_assignment_status,
    update_assignment,
    update_problem,
)
from db.homework_submissions import list_submissions_for_assignment
from homework.results import grading_label
from homework.review_views import REVIEW_SELECTION, review_submission_dialog
from components.compact_list import compact_list, close_compact_list
from homework.schema import authored_problems
from components.notifications import show_notices, show_success, observe_grading

logger = logging.getLogger(__name__)


def _student_name(user):
    user = user or {}
    name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))
    return name or "Unknown student"


def _format_timestamp(value):
    return value.strftime("%b %d, %Y %H:%M UTC") if hasattr(value, "strftime") else ""


def _require(result, message):
    if not result:
        raise ValueError(message)
    return result


def _show_error(error):
    logger.exception("Assignment operation failed")
    message = str(error) if isinstance(error, ValueError) else "Could not save or load the assignment. Try again."
    st.error(message)
    st.toast(message, icon=":material/error:")


def _render_submissions(assignment_id, professor_id):
    st.markdown("**Submissions**")
    if message := st.session_state.pop("professor_grading_notice", None):
        show_success(message)
    try:
        rows = list_submissions_for_assignment(assignment_id, professor_id)
    except (ValueError, RuntimeError, PyMongoError) as error:
        _show_error(error)
        return
    if not rows:
        st.info("No submissions yet.")
        return
    observe_grading(rows)
    st.caption(f"{len(rows)} submitted attempt{'s' if len(rows) != 1 else ''}.")
    def render_attempt(attempt):
        with st.container(border=True):
            identity, score, action = st.columns([3, 2, 2], vertical_alignment="center")
            identity.write(_student_name(attempt.get('user')))
            identity.caption(_format_timestamp(attempt.get('submitted_at')))
            score.caption(grading_label(attempt))
            if action.button("Review and grade", key=f"review_submission_{attempt['_id']}", icon=":material/grading:"):
                close_compact_list()
                st.session_state[REVIEW_SELECTION] = {
                    "assignment_id": str(assignment_id), "submission_id": str(attempt["_id"]),
                    "revision": attempt.get("professor_grade_revision", 0),
                }
                st.rerun()
    compact_list(rows, render_attempt, title="More submissions", key=f"professor_submissions_{assignment_id}")


def show_assignment_editor(assignment_id, professor_id: str):
    show_notices()
    return_page = st.session_state.get("professor_assignment_return_page", "app_pages/assignments.py")
    if st.button("Back to course" if return_page == "app_pages/course.py" else "Back to assignments",
                 key="back_to_assignments", icon=":material/arrow_back:", type="tertiary"):
        st.session_state.pop("selected_assignment_id", None)
        st.switch_page(return_page)

    try:
        assignment = get_assignment(assignment_id)
    except (ValueError, RuntimeError, PyMongoError) as error:
        _show_error(error)
        return

    if not assignment or assignment.get("professor_id") != professor_id:
        st.error("Assignment not found.")
        return

    assignment_key = str(assignment_id)
    current_status = assignment.get("status", "draft")
    with st.container(horizontal=True, vertical_alignment="center"):
        st.title(assignment.get("title", "Assignment"))
        st.badge(current_status.capitalize(), color=status_color(current_status))
    if message := st.session_state.pop("professor_assignment_success", None):
        show_success(message)
    is_draft = assignment.get("status", "draft") == "draft"
    st.caption("Save each question before switching questions or publishing the assignment.")

    details_tab, problems_tab, submissions_tab = st.tabs(["Details", "Problems", "Submissions"])
    with details_tab:
        with st.form(f"assignment_{assignment_key}"):
            title = st.text_input("Title", value=assignment.get("title", ""))
            description = st.text_area(
                "Description", value=assignment.get("description", "")
            )
            posted_column, due_column = st.columns(2)
            posted = posted_column.date_input(
                "Posted date", value=assignment.get("posted") or "today",
                help="Students can see this assignment starting on this date (UTC).",
            )
            due_date = due_column.date_input(
                "Due date", value=assignment.get("due_date"),
                help="Deadline: midnight UTC at the start of the selected date. Late submissions are accepted.",
            )
            with st.container(horizontal=True):
                save_assignment = st.form_submit_button(
                    "Post homework" if is_draft else "Save assignment", type="primary", icon=":material/save:",
                )
                finish_later = st.form_submit_button("Finish later", icon=":material/schedule:")

        if save_assignment or finish_later:
            try:
                if not title.strip():
                    raise ValueError("Assignment title is required.")
                if posted is None or due_date is None:
                    raise ValueError("Posted date and due date are required.")
                if due_date < posted:
                    raise ValueError("Due date cannot be before the posted date.")
                status = current_status if finish_later or current_status == "closed" else "published"
                if status != "draft" and not assignment.get("problems"):
                    raise ValueError("At least one problem is required. Add a problem before saving.")
                if status != "draft":
                    authored_problems(assignment["problems"])
                saved = update_assignment(
                    assignment_id,
                    professor_id,
                    title,
                    description,
                    status,
                    posted=posted,
                    due_date=due_date,
                )
                if not saved:
                    raise ValueError("Assignment could not be saved. Reload and try again.")
                st.session_state.professor_assignment_success = (
                    "Draft saved." if status == "draft" else "Homework saved (available from the posted date)."
                )
                if finish_later:
                    st.session_state.pop("selected_assignment_id", None)
                    st.switch_page(return_page)
                st.rerun()
            except (ValueError, RuntimeError, PyMongoError) as error:
                _show_error(error)

        with st.expander("Assignment settings"):
            if current_status == "published":
                status_label, new_status = "Close assignment", "closed"
            elif current_status == "closed":
                status_label, new_status = "Reopen assignment", "published"
            else:
                status_label = new_status = None
            if status_label and st.button(status_label, key=f"status_{assignment_key}"):
                try:
                    if not set_assignment_status(assignment_id, professor_id, new_status):
                        raise ValueError("Assignment status could not be saved. Reload and try again.")
                except (ValueError, RuntimeError, PyMongoError) as error:
                    _show_error(error)
                else:
                    st.session_state.professor_assignment_success = "Assignment closed." if new_status == "closed" else "Assignment reopened."
                    st.rerun()

            confirm_delete = st.checkbox("Confirm assignment deletion")
            if st.button("Delete assignment", disabled=not confirm_delete):
                try:
                    if delete_assignment(assignment_id, professor_id):
                        st.session_state.professor_assignment_success = "Assignment deleted."
                        st.session_state.pop("selected_assignment_id", None)
                        st.switch_page(return_page)
                    else:
                        raise ValueError("Assignment could not be deleted. Reload and try again.")
                except (ValueError, RuntimeError, PyMongoError) as error:
                    _show_error(error)


    with problems_tab:
        if is_draft:
            st.caption("Students see these questions once the assignment is posted.")
        problem_manager(
            assignment.get("problems", []),
            key=assignment_key,
            save=lambda problem_id, problem: _require(
                update_problem(assignment_id, professor_id, problem_id, problem),
                "Problem could not be saved. Reload and try again."),
            remove=lambda problem_id: _require(
                delete_problem(assignment_id, professor_id, problem_id),
                "Problem could not be removed. Reload and try again."),
            add=lambda problem: _require(
                add_problem(assignment_id, professor_id, problem),
                "Problem could not be added. Reload and try again."),
            min_problems=1,
        )

    with submissions_tab:
        _render_submissions(assignment_id, professor_id)
    selection = st.session_state.get(REVIEW_SELECTION)
    if selection and selection["assignment_id"] == str(assignment_id):
        review_submission_dialog(selection["submission_id"], selection["revision"])
