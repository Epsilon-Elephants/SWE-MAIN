"""Completion history. Each call records a scored attempt, including repeat attempts."""

import math
from datetime import datetime, timezone

from db.DataBase import db
from db.assignments import _student_visibility


def complete_assignment(assignment_id, user_id, score):
    """Record a server-calculated score for posted homework in an enrolled class.

    Scores are nonnegative points, with no assumed percentage scale. The completion
    timestamp is generated here; due dates never prevent a student from finishing.
    """
    if not assignment_id or not user_id:
        raise ValueError("Assignment ID and user ID are required.")
    assignment_id = db._object_id(assignment_id, "assignment ID")
    user_id = db._object_id(user_id, "user ID")
    if isinstance(score, bool):
        raise ValueError("Score must be a finite, nonnegative number.")
    try:
        score = float(score)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("Score must be a finite, nonnegative number.") from error
    if not math.isfinite(score) or score < 0:
        raise ValueError("Score must be a finite, nonnegative number.")

    completed_at = datetime.now(timezone.utc)
    assignment = db.read_one("assignments", {
        "_id": assignment_id, **_student_visibility(completed_at),
    })
    if assignment is None:
        raise ValueError("Assignment is not available to students.")
    student = db.read_one("users", {"_id": user_id, "permissions": "student"})
    membership = db.read_one("students", {
        "user_id": user_id, "class_id": assignment.get("class_id"),
    })
    if student is None or membership is None:
        raise ValueError("Student must be enrolled in the assignment's class.")

    return db.insert_one("completed_assignments", {
        "assignment_id": assignment_id,
        "user_id": user_id,
        "score": score,
        "completed_at": completed_at,
    })


def list_completed_assignments_for_user(user_id):
    if not user_id:
        raise ValueError("User ID is required.")
    return list(db.find("completed_assignments", {
        "user_id": db._object_id(user_id, "user ID"),
    }))


def list_completions_for_assignment(assignment_id):
    if not assignment_id:
        raise ValueError("Assignment ID is required.")
    return list(db.find("completed_assignments", {
        "assignment_id": db._object_id(assignment_id, "assignment ID"),
    }))


def summarize_completions(assignment_ids):
    """Return {assignment_id: {"students": n, "attempts": m}} for the given assignments.

    Used by the professor dashboard to show submission counts on assignment cards
    in a single round trip instead of one query per assignment.
    """
    object_ids = [db._object_id(value, "assignment ID") for value in assignment_ids or []]
    if not object_ids:
        return {}
    rows = db.aggregate("completed_assignments", [
        {"$match": {"assignment_id": {"$in": object_ids}}},
        {"$group": {
            "_id": "$assignment_id",
            "attempts": {"$sum": 1},
            "students": {"$addToSet": "$user_id"},
        }},
        {"$project": {"attempts": 1, "students": {"$size": "$students"}}},
    ])
    return {
        row["_id"]: {"students": row["students"], "attempts": row["attempts"]}
        for row in rows
    }


def list_submissions_for_assignment(assignment_id):
    """Return one row per student: best score, latest score, attempt count, last completion.

    Rows include the student's name and email and are sorted by last name.
    """
    if not assignment_id:
        raise ValueError("Assignment ID is required.")
    assignment_id = db._object_id(assignment_id, "assignment ID")
    return db.aggregate("completed_assignments", [
        {"$match": {"assignment_id": assignment_id}},
        {"$sort": {"completed_at": 1}},
        {"$group": {
            "_id": "$user_id",
            "attempts": {"$sum": 1},
            "best_score": {"$max": "$score"},
            "latest_score": {"$last": "$score"},
            "last_completed": {"$last": "$completed_at"},
        }},
        {"$lookup": {
            "from": "users",
            "localField": "_id",
            "foreignField": "_id",
            "as": "user",
            "pipeline": [{"$project": {"first_name": 1, "last_name": 1, "email": 1}}],
        }},
        {"$set": {"user": {"$arrayElemAt": ["$user", 0]}}},
        {"$sort": {"user.last_name": 1, "user.first_name": 1, "_id": 1}},
    ])
