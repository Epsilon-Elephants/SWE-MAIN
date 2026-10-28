"""Shared presentation of student-safe scores; private grading context stays server-side."""

from datetime import datetime, timezone

import streamlit as st

from homework.grading import grade_submission


def grading_label(submission):
    status = submission.get("grading_status", "ungraded")
    result = submission.get("grading_result") or {}
    if status == "graded" and result:
        return f"AI score: {result['total_points']:g}/{result['max_points']:g} points · {result['percentage']:g}%"
    return {
        "ungraded": "Awaiting grading", "grading": "Grading in progress",
        "failed": "Grading unavailable · retry available",
        "blocked": "Awaiting professor reference answers",
    }.get(status, "Awaiting grading")


def show_problem_result(submission, problem_id):
    if submission.get("grading_status") != "graded":
        return
    result = next((row for row in submission.get("grading_result", {}).get("problems", []) if row["problem_id"] == problem_id), None)
    if result:
        st.caption(f"AI score: {result['points_awarded']:g}/{result['max_points']:g} points")
        st.text(result["feedback"])


def grading_action(submission, actor_id):
    """Only explicit submit/retry actions call Rocky, never ordinary page reruns."""
    status = submission.get("grading_status", "ungraded")
    if status == "graded":
        return
    lease = submission.get("grading_lease_until")
    busy = status == "grading" and (lease is None or lease.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc))
    if status == "blocked":
        st.info("Your work is saved. The professor must supply reference answers before it can be graded.")
    elif status == "failed":
        st.warning("Your work is saved. Rocky could not finish grading; you can retry this attempt.")
    if st.button("Retry grading" if status in ("failed", "grading", "blocked") else "Grade submission",
                 key=f"grade_submission_{submission['_id']}", disabled=busy):
        with st.spinner("Rocky is grading the saved answers…"):
            grade_submission(submission["_id"], actor_id)
        st.rerun()
