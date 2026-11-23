"""Student homework views; private grading fields stay on the server."""

import logging
from datetime import timezone

import streamlit as st
from pymongo.errors import PyMongoError

from components.logic_symbol_editor import logic_symbol_editor
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
from components.notifications import notify, observe_grading, track_grading
from components.grade_book import kept_summary
from homework.grades import group_attempts


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
        attempts_by_assignment = group_attempts(submissions)
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
            kept, kept_label, _ = kept_summary(attempts_by_assignment.get(assignment["_id"], []))
            status = kept_label if kept else grading_label(submission) if submission else "Not submitted"
            def open_assignment():
                close_compact_list()
                st.session_state.homework_assignment_id = str(assignment["_id"])
                st.session_state.homework_return_page = "app_pages/homework.py"
                st.switch_page("app_pages/homework_assignment.py")
            assignment_row(assignment["title"], classes.get(assignment["class_id"], "Course") + f" · Due {format_date(assignment.get('due_date'), tz)}",
                           status, key=f"homework_open_{assignment['_id']}", open_assignment=open_assignment)
        compact_list(ordered, render_assignment, title="More homework", key="homework_list", columns=2)
    except ERRORS as error:
        if isinstance(error, ValueError):
            st.error(str(error))
        else:
            logging.exception("Homework database operation failed")
            st.error("Homework is unavailable right now. Please try again.")


ATTEMPTS_DIALOG = "homework_attempts_dialog"


@st.fragment(run_every="5s")
def show_submission_history(assignment_id):
    """Auto-refreshing grade line: the grade that counts plus the newest attempt's status."""
    user = student_user()
    try:
        get_homework_for_student(assignment_id, user["id"])
        history = list_submissions_for_student(user["id"], assignment_id)
        observe_grading(history)
        if not history:
            return
        kept, label, color = kept_summary(history)
        count = f"{len(history)} attempt{'s' if len(history) != 1 else ''}"
        st.markdown(f"**Your grade** :{color}-badge[{label}] · {count}")
        if kept is None or history[0]["_id"] != kept["_id"]:
            st.caption(f"Newest attempt: {grading_label(history[0])}")
        if history[0].get("grading_status") in {"failed", "blocked"}:
            # Problems the student can act on stay visible; routine processing does not.
            grading_action(history[0], user["id"])
        st.caption("Your highest score counts until your professor confirms a grade.")
    except ERRORS:
        st.error("Could not refresh saved submissions. Try again shortly.")


def _close_attempts():
    st.session_state.pop(ATTEMPTS_DIALOG, None)


@st.dialog("Your attempts", width="large", on_dismiss=_close_attempts)
def attempts_dialog(assignment_id, user_id):
    tz = user_tz()
    try:
        history = list_submissions_for_student(user_id, assignment_id)
    except ERRORS:
        st.error("Could not load your attempts. Try again shortly.")
        return
    if not history:
        st.caption("No attempts yet.")
        return
    kept = kept_summary(history)[0]
    by_id = {str(row["_id"]): row for row in history}

    def describe(sid):
        number = len(history) - list(by_id).index(sid)
        return f"Attempt {number} · {format_date(by_id[sid]['submitted_at'], tz)}" + (" · counts" if kept and by_id[sid]["_id"] == kept["_id"] else "")
    # Open on the attempt that counts, since that's the feedback students look for first.
    selected = st.selectbox("Attempt", list(by_id), format_func=describe, key=f"attempt_{assignment_id}",
                            index=list(by_id).index(str(kept["_id"])) if kept else 0)
    attempt = by_id[selected]
    st.badge(grading_label(attempt), color="blue" if attempt.get("grading_status") == "graded" else "gray")
    responses = {row["problem_id"]: row["answer"] for row in attempt["answers"]}
    for number, problem in enumerate(attempt["assignment_snapshot"]["problems"], 1):
        with st.container(border=True):
            st.markdown(f"**Question {number}**")
            st.write(problem["content"])
            st.text(responses.get(problem["problem_id"], ""))
            show_problem_result(attempt, problem["problem_id"])
    grading_action(attempt, user_id)
    if st.button("Close", key=f"close_attempts_{assignment_id}"):
        _close_attempts()
        st.rerun()


def show_homework_assignment():
    user = student_user()
    return_page = st.session_state.get("homework_return_page", "app_pages/homework.py")
    back_label = {"app_pages/course.py": "Back to course", "app_pages/practice.py": "Back to practice"}.get(return_page, "Back to homework")
    if st.button(back_label, icon=":material/arrow_back:"):
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
        st.title(assignment["title"])
        problems = show_details(assignment, classroom.get("name", "Class unavailable"), bool(history))
        if history:
            with st.container(border=True):
                show_submission_history(assignment_id)
                if st.button("View attempts and feedback", icon=":material/history:", key=f"view_attempts_{assignment_id}"):
                    st.session_state[ATTEMPTS_DIALOG] = assignment_id
            if st.session_state.get(ATTEMPTS_DIALOG) == assignment_id:
                attempts_dialog(assignment_id, user["id"])
        answers = {}
        # Once something is submitted, keep the page short: a new attempt is opt-in.
        answer_area = st.expander("Submit another attempt", icon=":material/edit_note:") if history else st.container()
        # Include the user ID so answers cannot carry over to another login.
        with answer_area, st.form(f"homework_answers_{user['id']}_{assignment_id}"):
            st.caption("Answer every question, then submit. Rocky grades in the background, so you can leave this page.")
            for number, problem in enumerate(problems, 1):
                st.subheader(f"Question {number}")
                st.write(problem["content"])
                st.caption(f"{problem['points']:g} points" + (f" · {problem['topic']}" if problem["topic"] else ""))
                answers[problem["problem_id"]] = logic_symbol_editor(
                    f"Answer to question {number}",
                    key=f"homework_answer_{user['id']}_{assignment_id}_{problem['problem_id']}",
                )
            submitted = st.form_submit_button("Submit homework", type="primary", icon=":material/send:")
        if submitted:
            submission_id = submit_homework(assignment_id, user["id"], answers)
            track_grading(submission_id)
            notify("Homework submitted. Rocky is grading it now; you'll get a banner when scores are ready.",
                   icon=":material/send:")
            st.rerun()
    except ERRORS as error:
        if isinstance(error, ValueError):
            st.error(str(error))
        else:
            logging.exception("Homework database operation failed")
            st.error("Homework is unavailable right now. Please try again.")
