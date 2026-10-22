"""Student homework views; private grading fields stay on the server."""

import logging
from datetime import datetime, timezone

import streamlit as st
from pymongo.errors import PyMongoError

from db.DataBase import db
from db.assignments import list_assignments_for_student
from db.homework_submissions import (
    get_homework_for_student, list_submissions_for_student, submit_homework,
)
from homework.schema import normalize_problems


ERRORS = (ValueError, RuntimeError, PyMongoError)


def student_user():
    user = st.session_state.get("user") or {}
    if user.get("permissions") != "student" or not user.get("id"):
        st.error("Sign in with a student account to view homework.")
        st.stop()
    return user


def format_date(value):
    if value is None:
        return "Not set"
    return value.strftime("%b %d, %Y, %H:%M UTC")


def show_details(assignment, class_name):
    st.caption(f"Class: {class_name}")
    if assignment.get("description"):
        st.write(assignment["description"])
    st.caption(
        f"Posted: {format_date(assignment.get('posted'))} · "
        f"Due: {format_date(assignment.get('due_date'))}"
    )
    problems = normalize_problems(assignment.get("problems"))
    st.caption(f"{len(problems)} questions · {sum(p['points'] for p in problems):g} points")
    due = assignment.get("due_date")
    if due and due.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        st.caption("Past due · Late submissions are accepted.")
    return problems


def show_homework_list():
    user = student_user()
    if st.button("Back to dashboard", icon=":material/arrow_back:"):
        st.switch_page("pages/home.py")
    st.title("Homework")
    st.caption("Open your homework to answer questions and submit your work.")
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
        for assignment in sorted(assignments, key=lambda row: (row.get("due_date") is None, str(row.get("due_date", "")))):
            with st.container(border=True):
                st.subheader(assignment["title"])
                show_details(assignment, classes.get(assignment["class_id"], "Class unavailable"))
                submission = latest.get(assignment["_id"])
                if submission:
                    st.caption(f"Submitted: {format_date(submission['submitted_at'])} · Awaiting grading")
                else:
                    st.caption("Not submitted")
                if st.button("Open homework", key=f"homework_open_{assignment['_id']}", icon=":material/assignment:"):
                    st.session_state.homework_assignment_id = str(assignment["_id"])
                    st.switch_page("pages/homework_assignment.py")
    except ERRORS as error:
        if isinstance(error, ValueError):
            st.error(str(error))
        else:
            logging.exception("Homework database operation failed")
            st.error("Homework is unavailable right now. Please try again.")


def show_homework_assignment():
    user = student_user()
    if st.button("Back to homework", icon=":material/arrow_back:"):
        st.switch_page("pages/homework.py")
    assignment_id = st.session_state.get("homework_assignment_id")
    if not assignment_id:
        st.info("Select an assignment from Homework first.")
        return
    try:
        assignment = get_homework_for_student(assignment_id, user["id"])
        classroom = db.read_one("classes", {"_id": assignment["class_id"]}) or {}
        history = list_submissions_for_student(user["id"], assignment_id)
        st.title(assignment["title"])
        problems = show_details(assignment, classroom.get("name", "Class unavailable"))
        if history:
            st.success("Your homework has been submitted. It is awaiting grading.")
            st.caption("You can submit another attempt. Each submitted attempt is saved separately.")
            with st.expander(f"Submitted attempts ({len(history)})"):
                for attempt in history:
                    st.write(f"Submitted {format_date(attempt['submitted_at'])} · Ungraded")
                    responses = {row["problem_id"]: row["answer"] for row in attempt["answers"]}
                    for number, problem in enumerate(attempt["assignment_snapshot"]["problems"], 1):
                        st.markdown(f"**Question {number}**")
                        st.write(problem["content"])
                        st.text(responses.get(problem["problem_id"], ""))
        st.info("Answer every question before submitting. Your work will be saved for grading; grading is not available yet.")
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
