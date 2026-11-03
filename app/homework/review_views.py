"""Focused professor grading dialog; private answers never enter student views."""

import logging

import streamlit as st
from pymongo.errors import PyMongoError

from db.DataBase import db
from homework.grades import effective_grade
from homework.results import grading_action, grading_label
from homework.review import get_submission_for_review, restore_rocky_grade, save_professor_grade

logger = logging.getLogger(__name__)
REVIEW_SELECTION = "professor_submission_review"


def close_review():
    st.session_state.pop(REVIEW_SELECTION, None)


def _finish_review(message):
    close_review()
    st.session_state.professor_grading_notice = message
    st.rerun()


@st.dialog("Review student assignment", width="large", on_dismiss=close_review)
def review_submission_dialog(submission_id, expected_revision):
    user = st.session_state.get("user") or {}
    if user.get("permissions") != "professor" or not user.get("id"):
        st.error("Sign in with a professor account to review submissions.")
        return
    try:
        submission = get_submission_for_review(submission_id, user["id"])
        student = db.read_one("users", {"_id": submission["user_id"]}) or {}
    except ValueError as error:
        st.error(str(error))
        return
    except (RuntimeError, PyMongoError):
        st.error("Could not load this submission. Close and reopen the review to try again.")
        return

    snapshot = submission["assignment_snapshot"]
    name = " ".join(filter(None, [student.get("first_name"), student.get("last_name")])) or "Unknown student"
    st.subheader(snapshot["title"])
    st.caption(f"{name} · {student.get('email', '')}")
    st.caption(f"Submitted {submission['submitted_at'].strftime('%b %d, %Y %H:%M UTC')}")
    st.write(grading_label(submission))
    rocky_grade = submission.get("grading_result") or {}
    final_grade = effective_grade(submission) or {}
    ready = submission.get("grading_status") == "graded" and bool(rocky_grade)
    editing = False
    if ready:
        rocky_column, final_column = st.columns(2)
        rocky_column.metric("Rocky's grade", f"{rocky_grade['total_points']:g}/{rocky_grade['max_points']:g} points")
        final_column.metric("Current published grade", f"{final_grade['total_points']:g}/{final_grade['max_points']:g} points")
        editing = st.toggle("Override Rocky's grade", value=bool(submission.get("professor_grade")),
                            help="Changes take effect after saving. To remove a saved override, choose Use Rocky's original grade.",
                            key=f"override_enabled_{submission_id}_{expected_revision}")
        if editing:
            st.caption("Adjust scores or feedback below, then save once for this attempt. The published grade will be labeled as a professor grade.")
    else:
        st.info("You can review the answers now. Once Rocky finishes, refresh to see its scores and override them.")
        st.button("Refresh Rocky's grade", key=f"refresh_review_{submission_id}")

    answers = {row["problem_id"]: row["answer"] for row in submission["answers"]}
    rocky_results = {row["problem_id"]: row for row in rocky_grade.get("problems", [])}
    final_results = {row["problem_id"]: row for row in final_grade.get("problems", [])}
    context = {row["problem_id"]: row for row in submission.get("grading_context", [])}
    scores, feedback = {}, {}
    with (st.form(f"professor_grade_{submission_id}_{expected_revision}") if editing else st.container()):
        for number, problem in enumerate(snapshot["problems"], 1):
            identifier = problem["problem_id"]
            with st.container(border=True):
                st.subheader(f"Question {number}")
                st.write(problem["content"])
                st.caption(f"{problem['points']:g} points")
                student_column, reference_column = st.columns(2)
                with student_column:
                    st.markdown("**Student answer**")
                    st.text(answers.get(identifier, ""))
                with reference_column:
                    st.markdown("**Professor answer**")
                    reference = context.get(identifier, problem)
                    st.write(reference.get("reference_answer") or "No reference answer was supplied for this attempt.")
                    if guidance := reference.get("grading_guidance"):
                        st.caption("Grading guidance")
                        st.write(guidance)
                rocky_result = rocky_results.get(identifier)
                if rocky_result:
                    st.markdown(f"**Rocky's grade: {rocky_result['points_awarded']:g}/{rocky_result['max_points']:g} points**")
                    st.text(rocky_result["feedback"])
                else:
                    st.caption("Rocky's grade: pending")
                if editing:
                    current = final_results[identifier]
                    scores[identifier] = st.number_input(
                        f"Professor score · question {number}", min_value=0.0, max_value=float(problem["points"]),
                        value=float(current["points_awarded"]),
                        key=f"professor_score_{submission_id}_{expected_revision}_{identifier}",
                    )
                    feedback[identifier] = st.text_area(
                        f"Feedback to student · question {number}", value=current["feedback"], max_chars=2000,
                        key=f"professor_feedback_{submission_id}_{expected_revision}_{identifier}",
                    )
        save = False
        if editing:
            reason = st.text_area("Reason for override", value=(submission.get("professor_grade") or {}).get("reason", ""),
                                  max_chars=2000, help="Saved for professor review; students see the scores and feedback above.",
                                  key=f"professor_reason_{submission_id}_{expected_revision}")
            save = st.form_submit_button("Save professor override", type="primary")
    try:
        if save:
            save_professor_grade(submission_id, user["id"], scores, feedback, reason, expected_revision=expected_revision)
            _finish_review("Professor grade saved. The student can now see the updated scores and feedback.")
        if submission.get("professor_grade") and st.button("Use Rocky's original grade", key=f"restore_rocky_{submission_id}"):
            restore_rocky_grade(submission_id, user["id"], expected_revision=expected_revision)
            _finish_review("Rocky's original grade is now published.")
        if not ready:
            grading_action(submission, user["id"])
    except ValueError as error:
        st.error(str(error))
    except (RuntimeError, PyMongoError) as error:
        logger.warning("Professor grading operation failed (%s)", type(error).__name__)
        st.error("Could not save this grade. Close and reopen the review to check its status before retrying.")
    if st.button("Close review", key=f"close_review_{submission_id}"):
        close_review()
        st.rerun()
