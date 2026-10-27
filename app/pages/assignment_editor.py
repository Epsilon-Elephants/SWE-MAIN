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
from db.homework_submissions import list_homework_submissions_for_professor

logger = logging.getLogger(__name__)


def _student_name(user):
    user = user or {}
    name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))
    return name or "Unknown student"


def _format_timestamp(value):
    return value.strftime("%b %d, %Y %H:%M UTC") if hasattr(value, "strftime") else ""


def _show_error(error):
    logger.exception("Assignment operation failed")
    st.error(str(error) if isinstance(error, ValueError) else "Could not save or load the assignment. Try again.")


def _render_submissions(assignment_id, professor_id):
    st.markdown("**Submissions**")
    try:
        rows = list_homework_submissions_for_professor(assignment_id, professor_id)
    except (ValueError, RuntimeError, PyMongoError) as error:
        _show_error(error)
        return
    if not rows:
        st.info("No submissions yet.")
        return
    st.caption(f"{len(rows)} submitted attempt(s). Scores will appear after grading is connected.")
    st.dataframe([
        {"Student": _student_name(row.get("user")),
         "Email": (row.get("user") or {}).get("email", ""),
         "Submitted": _format_timestamp(row.get("submitted_at")),
         "Grading": row.get("grading_status", "ungraded")}
        for row in rows
    ], hide_index=True, width="stretch")
    students = {}
    for row in rows:
        students.setdefault(str(row["user_id"]), []).append(row)

    def student_label(student_id):
        user = students[student_id][0].get("user") or {}
        email = user.get("email")
        return f"{_student_name(user)} · {email}" if email else _student_name(user)

    student_id = st.selectbox(
        "Student", options=list(students), format_func=student_label,
        key=f"review_student_{assignment_id}",
    )
    attempts = {str(row["_id"]): row for row in students[student_id]}
    selected = st.selectbox(
        "Submission", options=list(attempts),
        format_func=lambda attempt_id: f"{_format_timestamp(attempts[attempt_id].get('submitted_at'))} · {attempt_id[-6:]}",
        key=f"review_submission_{assignment_id}_{student_id}",
    )
    attempt = attempts[selected]
    responses = {row["problem_id"]: row["answer"] for row in attempt.get("answers", [])}
    for number, problem in enumerate(attempt.get("assignment_snapshot", {}).get("problems", []), 1):
        with st.container(border=True):
            st.markdown(f"**Question {number}**")
            st.write(problem["content"])
            st.text(responses.get(problem["problem_id"], ""))
            with st.expander("Instructor grading reference"):
                st.write(problem.get("reference_answer") or "No reference answer recorded.")
                st.write(problem.get("grading_guidance") or "No grading guidance recorded.")


def show_assignment_editor(assignment_id, professor_id: str):
    if st.button("Back to assignments", key="back_to_assignments"):
        st.session_state.pop("selected_assignment_id", None)
        st.switch_page("pages/home.py")

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
    st.subheader("Assignment editor")
    st.caption(f"Status: {current_status.capitalize()}")
    if message := st.session_state.pop("professor_assignment_success", None):
        st.success(message)
    is_draft = assignment.get("status", "draft") == "draft"
    st.caption("Save changes to individual problems below before posting or finishing later.")

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
                    st.switch_page("pages/home.py")
                st.rerun()
            except (ValueError, RuntimeError, PyMongoError) as error:
                _show_error(error)

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
                _show_error(error)
            else:
                st.rerun()

        confirm_delete = st.checkbox("Confirm assignment deletion")
        if st.button("Delete assignment", disabled=not confirm_delete):
            try:
                if delete_assignment(assignment_id, professor_id):
                    st.session_state.pop("selected_assignment_id", None)
                    st.switch_page("pages/home.py")
            except (ValueError, RuntimeError, PyMongoError) as error:
                _show_error(error)


    with problems_tab:
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
                problem_fields = grading_fields(content, problem)
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
                        problem_fields,
                    )
                    st.rerun()
                if remove_problem:
                    delete_problem(assignment_id, professor_id, problem_id)
                    st.rerun()
            except (ValueError, RuntimeError, PyMongoError) as error:
                _show_error(error)

        with st.form(f"new_problem_{assignment_key}", clear_on_submit=True):
            new_content = problem_editor(
                "New problem",
                key=f"new_content_{assignment_key}",
            )
            new_fields = grading_fields(new_content)
            add_submitted = st.form_submit_button("Add problem")

        if add_submitted:
            try:
                add_problem(assignment_id, professor_id, new_fields)
                st.rerun()
            except (ValueError, RuntimeError, PyMongoError) as error:
                _show_error(error)


    with submissions_tab:
        _render_submissions(assignment_id, professor_id)
