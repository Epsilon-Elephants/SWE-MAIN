"""Student overview data. Only public assignment fields leave this helper."""
from db.DataBase import db
from db.assignments import list_assignments_for_student
from db.homework_submissions import list_submissions_for_student


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
    submitted = {row["assignment_id"] for row in submissions}
    return {
        "classes": [
            {"Class": classes.get(row["class_id"], "Class unavailable"),
             "Earned points": (row.get("grade") or {}).get("earned", 0),
             "Possible points": (row.get("grade") or {}).get("possible", 0)}
            for row in memberships
        ],
        "assignments": [
            {"_id": row["_id"], "title": row["title"], "due_date": row.get("due_date"),
             "class_name": classes.get(row["class_id"], "Class unavailable"),
             "submitted": row["_id"] in submitted}
            for row in assignments
        ],
        "attempts": len(submissions),
        "awaiting_grading": sum(row.get("grading_status") == "ungraded" for row in submissions),
    }
