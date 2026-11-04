"""Professor-only review and validated, revision-checked grade overrides."""

import json
from datetime import datetime, timezone

from db.DataBase import db
from homework.grading import _authorized_submission
from homework.schema import normalize_problems
from rocky.grading import validate_grading_response


def get_submission_for_review(submission_id, professor_id):
    """Recheck the professor's current role and class ownership on every read."""
    return _authorized_submission(submission_id, professor_id, required_role="professor")


def _save_grade(submission, grade, expected_revision):
    revision = submission.get("professor_grade_revision", 0)
    if type(expected_revision) is not int or expected_revision != revision:
        raise ValueError("This grade has changed. Close and reopen the review before saving.")
    saved = db.update_one("homework_submissions", {
        "_id": submission["_id"], "grading_status": "graded",
        # MongoDB equality to null also matches documents created before revisions.
        "professor_grade_revision": submission.get("professor_grade_revision"),
    }, {"professor_grade": grade, "professor_grade_revision": revision + 1})
    if not saved.matched_count:
        raise ValueError("This grade has changed. Close and reopen the review before saving.")


def save_professor_grade(submission_id, professor_id, scores, feedback, reason, *, expected_revision):
    """Save a complete professor grade; totals and maxima always come from the server."""
    submission = get_submission_for_review(submission_id, professor_id)
    if submission.get("grading_status") != "graded" or not submission.get("grading_result"):
        raise ValueError("Wait for Rocky to finish grading before saving an override.")
    problems = normalize_problems(submission["assignment_snapshot"]["problems"])
    identifiers = {problem["problem_id"] for problem in problems}
    if not isinstance(scores, dict) or not isinstance(feedback, dict) or set(scores) != identifiers or set(feedback) != identifiers:
        raise ValueError("Provide a score and feedback for every problem in this submission.")
    if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 2000:
        raise ValueError("Enter a reason for the override (up to 2000 characters).")
    result = validate_grading_response(json.dumps({
        "schema_version": 1,
        "results": [{"problem_id": problem["problem_id"],
                     "points_awarded": scores[problem["problem_id"]],
                     "feedback": feedback[problem["problem_id"]]} for problem in problems],
    }), problems)
    result.update(graded_by=db._object_id(professor_id, "professor ID"),
                  graded_at=datetime.now(timezone.utc), reason=reason.strip())
    _save_grade(submission, result, expected_revision)
    return result


def restore_rocky_grade(submission_id, professor_id, *, expected_revision):
    """Publish the original AI grade again without another Rocky request."""
    submission = get_submission_for_review(submission_id, professor_id)
    if submission.get("grading_status") != "graded" or not submission.get("grading_result"):
        raise ValueError("Rocky's grade is not available yet.")
    _save_grade(submission, None, expected_revision)
