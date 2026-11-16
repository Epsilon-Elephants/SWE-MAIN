import logging

import streamlit as st
from pymongo.errors import PyMongoError

from components.problem_editor import grading_fields, problem_editor
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
from homework.schema import authored_problem, authored_problems
from components.notifications import show_notices, show_success, observe_grading

logger = logging.getLogger(__name__)


def _student_name(user):
    user = user or {}
    name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))
    return name or "Unknown student"


def _format_timestamp(value):
    return value.strftime("%b %d, %Y %H:%M UTC") if hasattr(value, "strftime") else ""


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
    if st.button("Back to course" if return_page == "app_pages/course.py" else "Back to assignments", key="back_to_assignments"):
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
    st.title(assignment.get("title", "Assignment"))
    st.caption(f"Status: {current_status.capitalize()}")
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
            posted = st.date_input(
                "Posted date", value=assignment.get("posted") or "today",
                help="Students can see this assignment starting on this date (UTC).",
            )
            due_date = st.date_input(
                "Due date", value=assignment.get("due_date"),
                help="Deadline: midnight UTC at the start of the selected date. Late submissions are accepted.",
            )
            save_assignment = st.form_submit_button(
                "Post homework" if is_draft else "Save assignment", type="primary",
            )
            finish_later = st.form_submit_button("Finish later")

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
        problems = assignment.get("problems", [])
        problem_options = [problem["problem_id"] for problem in problems] + ["new"]
        labels = {problem["problem_id"]: f"Question {number} · {problem['content'][:70]}" for number, problem in enumerate(problems, 1)}
        selected_problem = st.selectbox("Question", problem_options, format_func=lambda value: labels.get(value, "+ Add a question"), key=f"selected_problem_{assignment_key}")

        for number, problem in enumerate(assignment.get("problems", []), start=1):
            problem_id = problem.get("problem_id")
            if not problem_id or problem_id != selected_problem:
                continue

            with st.form(f"problem_{assignment_key}_{problem_id}"):
                content = problem_editor(
                    f"Problem {number}",
                    key=f"content_{assignment_key}_{problem_id}",
                    initial_content=problem.get("content", ""),
                )
                problem_fields = grading_fields(
                    content,
                    problem,
                    key_prefix=f"problem_{assignment_key}_{problem_id}",
                )
                save_problem = st.form_submit_button("Save problem")
                remove_problem = st.form_submit_button(
                    "Remove problem", disabled=len(assignment.get("problems", [])) <= 1,
                )

            try:
                if save_problem:
                    saved = update_problem(
                        assignment_id,
                        professor_id,
                        problem_id,
                        authored_problem(problem_fields, problem_id=problem_id),
                    )
                    if not saved:
                        raise ValueError("Problem could not be saved. Reload and try again.")
                    st.session_state.professor_assignment_success = "Problem saved."
                    st.rerun()
                if remove_problem:
                    if not delete_problem(assignment_id, professor_id, problem_id):
                        raise ValueError("Problem could not be removed. Reload and try again.")
                    st.session_state.professor_assignment_success = "Problem removed."
                    st.rerun()
            except (ValueError, RuntimeError, PyMongoError) as error:
                _show_error(error)

        if selected_problem == "new":
            new_problem_prefix = f"new_problem_{assignment_key}"
            new_problem_keys = (
                f"new_content_{assignment_key}",
                f"{new_problem_prefix}_points",
                f"{new_problem_prefix}_topic",
                f"{new_problem_prefix}_reference_answer",
                f"{new_problem_prefix}_grading_guidance",
            )
            if st.session_state.pop(f"{new_problem_prefix}_clear", False):
                for key in new_problem_keys:
                    st.session_state.pop(key, None)

            with st.form(f"new_problem_{assignment_key}"):
                new_content = problem_editor(
                    "New problem", key=f"new_content_{assignment_key}",
                )
                new_fields = grading_fields(
                    new_content, key_prefix=new_problem_prefix,
                )
                add_submitted = st.form_submit_button("Add problem")
            if add_submitted:
                try:
                    if not add_problem(assignment_id, professor_id, authored_problem(new_fields)):
                        raise ValueError("Problem could not be added. Reload and try again.")
                    st.session_state[f"{new_problem_prefix}_clear"] = True
                    st.session_state.professor_assignment_success = "Problem added."
                    st.rerun()
                except (ValueError, RuntimeError, PyMongoError) as error:
                    _show_error(error)


    with submissions_tab:
        _render_submissions(assignment_id, professor_id)
    selection = st.session_state.get(REVIEW_SELECTION)
    if selection and selection["assignment_id"] == str(assignment_id):
        review_submission_dialog(selection["submission_id"], selection["revision"])
