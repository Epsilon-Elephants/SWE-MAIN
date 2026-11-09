"""Student overview data. Only public assignment fields leave this helper."""
from db.DataBase import db
from db.assignments import list_assignments_for_student
from db.homework_submissions import list_submissions_for_student
from homework.grades import effective_grade
from homework.results import grading_label
from homework.study import submission_recommendations


def _latest_attempt(submission):
    """Student-safe summary of the latest attempt: when, a score label, and the percentage."""
    if submission is None:
        return {"submitted_at": None, "grade_label": None, "score_percentage": None}
    return {
        "submitted_at": submission.get("submitted_at"),
        "grade_label": grading_label(submission),
        "score_percentage": (effective_grade(submission) or {}).get("percentage"),
    }


def load_student_overview(user_id):
    user_id = db._object_id(user_id, "user ID")
    if db.read_one("users", {"_id": user_id, "permissions": "student"}) is None:
        raise ValueError("A student account is required.")
    memberships = list(db.find("students", {"user_id": user_id}))
    class_ids = [row["class_id"] for row in memberships]
    classes = {row["_id"]: row.get("name", "Untitled class") for row in db.find(
        "classes", {"_id": {"$in": class_ids}},
    )} if class_ids else {}
    assignments = list_assignments_for_student(user_id)
    submissions = list_submissions_for_student(user_id)
    # Submissions are sorted newest first, so the first one per assignment is the latest attempt.
    latest = {}
    for row in submissions:
        latest.setdefault(row["assignment_id"], row)
    return {
        "classes": [
            {"_id": row["class_id"], "Class": classes.get(row["class_id"], "Class unavailable"),
             "Earned points": (row.get("grade") or {}).get("earned", 0),
             "Possible points": (row.get("grade") or {}).get("possible", 0)}
            for row in memberships
        ],
        "assignments": [
            {"_id": row["_id"], "title": row["title"], "due_date": row.get("due_date"),
             "class_id": row["class_id"],
             "class_name": classes.get(row["class_id"], "Class unavailable"),
             "submitted": row["_id"] in latest,
             **_latest_attempt(latest.get(row["_id"]))}
            for row in assignments
        ],
        "attempts": len(submissions),
        "awaiting_grading": sum(row.get("grading_status") in {"ungraded", "grading", "blocked"}
                                 or bool(row.get("grading_retry_at")) for row in submissions),
        "recommendations": submission_recommendations(submissions),
    }
