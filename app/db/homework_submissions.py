"""Homework access, immutable answers, and saved grading results."""

from datetime import datetime, timezone

from db.DataBase import db
from db.assignments import _student_visibility
from homework.schema import SCHEMA_VERSION, normalize_problems


def get_homework_for_student(assignment_id, user_id):
    """Authorize every detail read and submit against current enrollment/visibility."""
    assignment_id = db._object_id(assignment_id, "assignment ID")
    user_id = db._object_id(user_id, "user ID")
    user = db.read_one("users", {"_id": user_id, "permissions": "student"})
    if user is None:
        raise ValueError("A student account is required.")
    assignment = db.read_one("assignments", {
        "_id": assignment_id, **_student_visibility(datetime.now(timezone.utc)),
    })
    if assignment is None:
        raise ValueError("Homework is not available.")
    membership = db.read_one("students", {"user_id": user_id, "class_id": assignment["class_id"]})
    if membership is None:
        raise ValueError("You must be enrolled in this class to access its homework.")
    return assignment


def list_submissions_for_student(user_id, assignment_id=None):
    query = {"user_id": db._object_id(user_id, "user ID")}
    if assignment_id is not None:
        query["assignment_id"] = db._object_id(assignment_id, "assignment ID")
    return sorted(db.find("homework_submissions", query), key=lambda row: row["submitted_at"], reverse=True)


def list_submissions_for_assignment(assignment_id, professor_id):
    """Read actual homework attempts only for the current owning instructor."""
    if not assignment_id or not professor_id:
        raise ValueError("Assignment and professor IDs are required.")
    assignment_id = db._object_id(assignment_id, "assignment ID")
    professor_id = db._object_id(professor_id, "professor ID")
    professor = db.read_one("users", {"_id": professor_id, "permissions": "professor"})
    assignment = db.read_one("assignments", {"_id": assignment_id, "professor_id": str(professor_id)})
    if professor is None or assignment is None:
        raise ValueError("Assignment is not available.")
    classroom = db.read_one("classes", {"_id": assignment["class_id"], "instructor_id": professor_id})
    if classroom is None:
        raise ValueError("You do not teach this assignment's class.")
    return db.aggregate("homework_submissions", [
        {"$match": {"assignment_id": assignment_id, "class_id": assignment["class_id"]}},
        {"$sort": {"submitted_at": -1, "_id": -1}},
        {"$lookup": {
            "from": "users", "localField": "user_id", "foreignField": "_id", "as": "user",
            "pipeline": [{"$project": {"first_name": 1, "last_name": 1, "email": 1}}],
        }},
        {"$set": {"user": {"$arrayElemAt": ["$user", 0]}}},
    ])


def summarize_submissions(assignment_ids):
    """Count saved homework attempts, including those waiting for grading."""
    object_ids = [db._object_id(value, "assignment ID") for value in assignment_ids or []]
    if not object_ids:
        return {}
    rows = db.aggregate("homework_submissions", [
        {"$match": {"assignment_id": {"$in": object_ids}}},
        {"$group": {"_id": "$assignment_id", "attempts": {"$sum": 1}, "students": {"$addToSet": "$user_id"}}},
        {"$project": {"attempts": 1, "students": {"$size": "$students"}}},
    ])
    return {row["_id"]: {"students": row["students"], "attempts": row["attempts"]} for row in rows}


def submit_homework(assignment_id, user_id, answers):
    """Validate all answers against current problems and save a new ungraded attempt.

    Accept only a problem-ID -> text mapping, never client scores or snapshots.
    Late and repeat submissions are allowed, matching existing completion policy.
    """
    assignment = get_homework_for_student(assignment_id, user_id)
    problems = normalize_problems(assignment.get("problems"))
    ids = {problem["problem_id"] for problem in problems}
    if not isinstance(answers, dict) or set(answers) != ids:
        raise ValueError("Homework questions have changed. Reopen the homework and answer every question.")
    responses = []
    for problem in problems:
        answer = answers[problem["problem_id"]]
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("Answer every question before submitting.")
        responses.append({"problem_id": problem["problem_id"], "answer": answer.strip()})
    return db.insert_one("homework_submissions", {
        "schema_version": SCHEMA_VERSION,
        "assignment_id": db._object_id(assignment_id, "assignment ID"),
        "user_id": db._object_id(user_id, "user ID"),
        "class_id": assignment["class_id"],
        "submitted_at": datetime.now(timezone.utc),
        "status": "submitted",
        "grading_status": "ungraded",
        "assignment_snapshot": {
            "title": assignment["title"],
            "description": assignment.get("description", ""),
            "posted": assignment.get("posted"),
            "due_date": assignment.get("due_date"),
            "problems": problems,
        },
        "answers": responses,
    })
