"""Authorized, retryable grading of saved homework without duplicate grade records."""

import copy
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from bson import ObjectId

from db.DataBase import db
from homework.schema import build_grading_payload, normalize_problems
from app.rocky.grading import InvalidGrade, grade_with_rocky

logger = logging.getLogger(__name__)
LEASE_DURATION = timedelta(minutes=10)


def _id(value, label):
    if not isinstance(value, (str, ObjectId)) or not value:
        raise ValueError(f"Invalid {label}.")
    return db._object_id(value, label)


def _authorized_submission(submission_id, actor_id):
    submission_id, actor_id = _id(submission_id, "submission ID"), _id(actor_id, "user ID")
    actor = db.read_one("users", {"_id": actor_id})
    role = (actor or {}).get("permissions")
    if role not in ("student", "professor"):
        raise ValueError("A student or professor account is required.")
    query = {"_id": submission_id}
    if role == "student":
        query["user_id"] = actor_id
    submission = db.read_one("homework_submissions", query)
    if submission is None:
        raise ValueError("Submission is not available.")
    if role == "student":
        membership = db.read_one("students", {"user_id": actor_id, "class_id": submission["class_id"]})
        if membership is None:
            raise ValueError("You must be enrolled in this class.")
    else:
        classroom = db.read_one("classes", {"_id": submission["class_id"], "instructor_id": actor_id})
        if classroom is None:
            raise ValueError("You do not teach this submission's class.")
    return submission


def _grading_payload(submission):
    """Keep the saved questions/points; fill only missing, matching references."""
    prepared = copy.deepcopy(submission)
    problems = normalize_problems(prepared["assignment_snapshot"]["problems"])
    if any(not problem["reference_answer"] for problem in problems):
        # Existing submissions may predate the instructor adding an answer key.
        # A changed question or maximum must never silently replace its snapshot.
        assignment = db.read_one("assignments", {"_id": submission["assignment_id"], "class_id": submission["class_id"]})
        current = normalize_problems(assignment["problems"]) if assignment and assignment.get("problems") else []
        by_id = {problem["problem_id"]: problem for problem in current}
        for problem in problems:
            replacement = by_id.get(problem["problem_id"])
            if (not problem["reference_answer"] and replacement
                    and problem["content"] == replacement["content"]
                    and problem["points"] == replacement["points"]):
                problem["reference_answer"] = replacement["reference_answer"]
                problem["grading_guidance"] = replacement["grading_guidance"]
    if any(not problem["reference_answer"] for problem in problems):
        return None
    prepared["assignment_snapshot"]["problems"] = problems
    answers = prepared.get("answers", [])
    if (len(answers) != len(problems) or {answer["problem_id"] for answer in answers} != {p["problem_id"] for p in problems}
            or any(not isinstance(answer.get("answer"), str) or not answer["answer"].strip() for answer in answers)):
        raise ValueError("Saved answers do not match the submission's problems.")
    return build_grading_payload(prepared)


def grade_submission(submission_id, actor_id, *, rocky_client=None, now=None):
    """Grade once, with an atomic lease and retry after failure or an expired lease.

    The caller supplies the authenticated actor ID, never client grades. A failure
    preserves the submitted answers and records a safe error code, never a zero.
    """
    submission = _authorized_submission(submission_id, actor_id)
    if submission.get("grading_status") == "graded":
        return "graded"
    now = now or datetime.now(timezone.utc)
    token = str(uuid4())
    claimed = db.update_one("homework_submissions", {
        "_id": submission["_id"],
        "$or": [
            {"grading_status": {"$in": ["ungraded", "failed", "blocked"]}},
            {"grading_status": "grading", "grading_lease_until": {"$lte": now}},
        ],
    }, {
        "grading_status": "grading", "grading_token": token,
        "grading_started_at": now, "grading_lease_until": now + LEASE_DURATION,
        "grading_error": None,
    })
    if claimed.matched_count == 0:
        return "grading"
    owned_query = {"_id": submission["_id"], "grading_status": "grading", "grading_token": token}
    try:
        payload = _grading_payload(submission)
        if payload is None:
            fields = {"grading_status": "blocked", "grading_error": "missing_reference"}
        else:
            result = grade_with_rocky(payload, rocky_client=rocky_client)
            result["graded_at"] = datetime.now(timezone.utc)
            fields = {
                "grading_status": "graded", "grading_error": None,
                "grading_result": result,
                # Private evidence of the exact rubric/reference used on retry.
                "grading_context": [{
                    key: problem[key] for key in ("problem_id", "reference_answer", "grading_guidance")
                } for problem in payload["problems"]],
            }
    except (ValueError, KeyError, TypeError) as error:
        logger.warning("Invalid grading data for submission %s (%s)", submission["_id"], type(error).__name__)
        fields = {"grading_status": "failed", "grading_error": "invalid_response" if isinstance(error, InvalidGrade) else "invalid_submission"}
    except Exception as error:
        logger.warning("Rocky grading unavailable for submission %s (%s)", submission["_id"], type(error).__name__)
        fields = {"grading_status": "failed", "grading_error": "service_unavailable"}
    saved = db.update_one("homework_submissions", owned_query, fields)
    return fields["grading_status"] if saved.matched_count else "grading"
