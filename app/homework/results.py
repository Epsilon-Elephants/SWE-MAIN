"""Shared presentation of student-safe scores; private grading context stays server-side."""

from datetime import datetime, timezone

import streamlit as st

from homework.grading import queue_grading
from homework.grades import effective_grade, confirmed_grade
from homework.study import practice_suggestion


def grading_label(submission):
    status = submission.get("grading_status", "ungraded")
    result = effective_grade(submission) or {}
    if status == "graded" and result:
        source = "Confirmed score" if confirmed_grade(submission) else "Tentative Rocky score"
        return f"{source}: {result['total_points']:g}/{result['max_points']:g} points · {result['percentage']:g}%"
    if status == "failed" and submission.get("grading_retry_at"):
        return "Processing · Rocky will retry automatically"
    return {
        "ungraded": "Processing · Waiting for Rocky", "grading": "Processing · Rocky is grading",
        "failed": "Grading unavailable · retry available",
        "blocked": "Awaiting professor reference answers",
    }.get(status, "Awaiting grading")


def show_problem_result(submission, problem_id):
    if submission.get("grading_status") != "graded":
        return
    result = next((row for row in (effective_grade(submission) or {}).get("problems", []) if row["problem_id"] == problem_id), None)
    if result:
        source = "Confirmed score" if confirmed_grade(submission) else "Tentative Rocky score"
        st.caption(f"{source}: {result['points_awarded']:g}/{result['max_points']:g} points")
        st.text(result["feedback"])
        problem = next(row for row in submission["assignment_snapshot"]["problems"] if row["problem_id"] == problem_id)
        st.caption(f"Recommended practice · {problem.get('topic') or 'This question'}")
        st.write(result.get("study_recommendation") or practice_suggestion(problem, result["points_awarded"]))


def grading_action(submission, actor_id):
    """Explicit retries queue saved work; the page never calls Rocky."""
    status = submission.get("grading_status", "ungraded")
    if status == "graded":
        return
    lease = submission.get("grading_lease_until")
    busy = status == "grading" and lease is not None and lease.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)
    if status == "ungraded" or busy or (status == "failed" and submission.get("grading_retry_at")):
        st.info("Your work is saved and processing. You can keep working or leave this page; scores, feedback, and practice suggestions will appear when Rocky finishes.")
        return
    if status == "blocked":
        st.info("Your work is saved. The professor must supply reference answers before it can be graded.")
    elif status == "failed":
        st.warning("Your work is saved. Rocky could not finish grading; you can retry this attempt.")
    if st.button("Retry grading", key=f"grade_submission_{submission['_id']}"):
        queue_grading(submission["_id"], actor_id)
        st.rerun()
