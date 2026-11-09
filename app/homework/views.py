"""Student homework views; private grading fields stay on the server."""

import logging
from datetime import timezone

import streamlit as st
from pymongo.errors import PyMongoError

from db.DataBase import db
from components.compact_list import compact_list, close_compact_list
from components.course_cards import assignment_row
from db.assignments import list_assignments_for_student
from db.homework_submissions import (
    get_homework_for_student, list_submissions_for_student, submit_homework,
)
from homework.schema import normalize_problems
from homework.results import grading_action, grading_label, show_problem_result

from pages.dashboards.student.due_dates import due_sort_key, due_status, resolve_timezone
from pages.dashboards.student.recently_visited import record_visit


ERRORS = (ValueError, RuntimeError, PyMongoError)


def student_user():
    user = st.session_state.get("user") or {}
    if user.get("permissions") != "student" or not user.get("id"):
        st.error("Sign in with a student account to view homework.")
        st.stop()
    return user


def user_tz():
    #browser timezone
    return resolve_timezone(getattr(st.context, "timezone", None))


def format_date(value, tz=None):
    if value is None:
        return "Not set"
    aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return aware.astimezone(tz or timezone.utc).strftime("%b %d, %Y, %H:%M %Z")


def show_due_badge(assignment, submitted=False):
    # show badge for due date status
    status = due_status(assignment.get("due_date"), tz=user_tz())
    if submitted:
        st.markdown(":green-badge[:material/check_circle: Submitted]")
    elif status.kind != "none":
        st.markdown(f":{status.color}-badge[{status.icon} {status.badge}]")
    return status


def show_details(assignment, class_name, submitted=False):
    tz = user_tz()
    st.caption(f"Class: {class_name}")
    if assignment.get("description"):
        st.write(assignment["description"])
    status = show_due_badge(assignment, submitted)
    st.caption(
        f"Posted: {format_date(assignment.get('posted'), tz)} · "
        f"Due: {format_date(assignment.get('due_date'), tz)}"
    )
    problems = normalize_problems(assignment.get("problems"))
    st.caption(f"{len(problems)} questions · {sum(p['points'] for p in problems):g} points")
    if status.kind == "overdue" and not submitted:
        st.caption("Late submissions are accepted.")
    return problems


def show_homework_list():
    user = student_user()
    if st.button("Back to dashboard", icon=":material/arrow_back:"):
        st.switch_page("app_pages/overview.py")
    st.title("Assignments")
    try:
        assignments = list_assignments_for_student(user["id"])
        submissions = list_submissions_for_student(user["id"])
        class_ids = list({row["class_id"] for row in assignments})
        classes = {row["_id"]: row["name"] for row in db.find("classes", {"_id": {"$in": class_ids}})} if class_ids else {}
        latest = {}
        for submission in submissions:
            latest.setdefault(submission["assignment_id"], submission)
        if not assignments:
            st.info("No homework is available yet. Posted homework from your enrolled classes will appear here.")
        tz = user_tz()
        late = sum(
            1 for row in assignments
            if row["_id"] not in latest and due_status(row.get("due_date"), tz=tz).kind == "overdue"
        )
        if late:
            st.warning(f"{late} assignment(s) overdue. Late work is still accepted, so submit as soon as you can.",
                       icon=":material/error:")
        # Unsubmitted work first (most overdue at the top), then submitted work.
        ordered = sorted(assignments, key=lambda row: (row["_id"] in latest, due_sort_key(row.get("due_date"))))
        search, group = st.columns([3, 2])
        query = search.text_input("Find an assignment", placeholder="Search assignments").strip().casefold()
        selected_group = group.selectbox("Show", ["All assignments", "To do", "Submitted"])
        ordered = [row for row in ordered if query in row["title"].casefold()
                   and (selected_group == "All assignments" or (row["_id"] in latest) == (selected_group == "Submitted"))]
        def render_assignment(assignment):
            submission = latest.get(assignment["_id"])
            status = grading_label(submission) if submission else "Not submitted"
            def open_assignment():
                close_compact_list()
                st.session_state.homework_assignment_id = str(assignment["_id"])
                st.session_state.homework_return_page = "app_pages/homework.py"
                st.switch_page("app_pages/homework_assignment.py")
            assignment_row(assignment["title"], classes.get(assignment["class_id"], "Course") + f" · Due {format_date(assignment.get('due_date'), tz)}",
                           status, key=f"homework_open_{assignment['_id']}", open_assignment=open_assignment)
        compact_list(ordered, render_assignment, title="More homework", key="homework_list")
    except ERRORS as error:
        if isinstance(error, ValueError):
            st.error(str(error))
        else:
            logging.exception("Homework database operation failed")
            st.error("Homework is unavailable right now. Please try again.")


@st.fragment(run_every="5s")
def show_submission_history(assignment_id):
    user = student_user()
    try:
        get_homework_for_student(assignment_id, user["id"])
        history = list_submissions_for_student(user["id"], assignment_id)
        if not history:
            return
        tz = user_tz()
        st.success(f"Your homework has been submitted. {grading_label(history[0])}")
        st.caption("You can submit another attempt. Each submitted attempt is saved separately.")
        def render_attempt(attempt):
            st.write(f"Submitted {format_date(attempt['submitted_at'], tz)} · {grading_label(attempt)}")
            responses = {row["problem_id"]: row["answer"] for row in attempt["answers"]}
            for number, problem in enumerate(attempt["assignment_snapshot"]["problems"], 1):
                st.markdown(f"**Question {number}**")
                st.write(problem["content"])
                st.text(responses.get(problem["problem_id"], ""))
                show_problem_result(attempt, problem["problem_id"])
            grading_action(attempt, user["id"])
        with st.expander(f"Submission details · {len(history)} attempt(s)"):
            by_id = {str(row["_id"]): row for row in history}
            selected = st.selectbox("Attempt", list(by_id), format_func=lambda sid: format_date(by_id[sid]["submitted_at"], tz), key=f"attempt_{assignment_id}")
            render_attempt(by_id[selected])
    except ERRORS:
        st.error("Could not refresh saved submissions. Try again shortly.")


def show_homework_assignment():
    user = student_user()
    return_page = st.session_state.get("homework_return_page", "app_pages/homework.py")
    if st.button("Back to course" if return_page == "app_pages/course.py" else "Back to homework", icon=":material/arrow_back:"):
        st.switch_page(return_page)
    assignment_id = st.session_state.get("homework_assignment_id")
    if not assignment_id:
        st.info("Select an assignment from Homework first.")
        return
    try:
        assignment = get_homework_for_student(assignment_id, user["id"])
        classroom = db.read_one("classes", {"_id": assignment["class_id"]}) or {}
        due = assignment.get("due_date")
        record_visit("homework", assignment_id, assignment["title"], class_name=classroom.get("name", ""), due=f"Due {format_date(due)}" if due else "No due date",)
        history = list_submissions_for_student(user["id"], assignment_id)
        tz = user_tz()
        st.title(assignment["title"])
        problems = show_details(assignment, classroom.get("name", "Class unavailable"), bool(history))
        show_submission_history(assignment_id)
        st.info("Answer every question before submitting. Your answers save immediately, then Rocky grades in the background and suggests what to practice next. You can keep working while it processes.")
        answers = {}
        # Include the user ID so answers cannot carry over to another login.
        with st.form(f"homework_answers_{user['id']}_{assignment_id}"):
            for number, problem in enumerate(problems, 1):
                st.subheader(f"Question {number}")
                st.write(problem["content"])
                st.caption(f"{problem['points']:g} points" + (f" · {problem['topic']}" if problem["topic"] else ""))
                answers[problem["problem_id"]] = st.text_area(
                    f"Answer to question {number}",
                    key=f"homework_answer_{user['id']}_{assignment_id}_{problem['problem_id']}",
                    height=160,
                )
            submitted = st.form_submit_button("Submit homework", type="primary", icon=":material/send:")
        if submitted:
            submit_homework(assignment_id, user["id"], answers)
            st.rerun()
    except ERRORS as error:
        if isinstance(error, ValueError):
            st.error(str(error))
        else:
            logging.exception("Homework database operation failed")
            st.error("Homework is unavailable right now. Please try again.")
