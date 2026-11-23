# Feedback and issue reports.

# Students and professors submit reports. 
from datetime import datetime, timedelta, timezone

from db.DataBase import db

CATEGORIES = {
    "bug": "Something is broken",
    "confusing": "Confusing or hard to use",
    "grading": "Grading question",
    "suggestion": "Suggestion",
}
STATUSES = {"new": "New", "in_progress": "In progress", "resolved": "Resolved"}

MIN_MESSAGE = 10
MAX_MESSAGE = 2000
MAX_NOTE = 1000
MAX_PAGE = 100
REPORTS_PER_HOUR = 5
LIST_LIMIT = 100


def _check_rate_limit(user_id, now):
    # Allow REPORTS_PER_HOUR reports per user, counted from the feedback collection itself.
    window = timedelta(hours=1)
    rows = db.aggregate("feedback", [
        {"$match": {"user_id": user_id, "created_at": {"$gte": now - window}}},
        {"$group": {"_id": None, "count": {"$sum": 1}, "oldest": {"$min": "$created_at"}}},
    ])
    if not rows or rows[0]["count"] < REPORTS_PER_HOUR:
        return
    oldest = rows[0]["oldest"]
    oldest = oldest.replace(tzinfo=timezone.utc) if oldest.tzinfo is None else oldest
    wait_seconds = max(0, (oldest + window - now).total_seconds())
    minutes = max(1, -(-int(wait_seconds) // 60))
    raise ValueError(f"You have sent several reports recently. Try again in about {minutes} minute(s).")


def submit_feedback(user_id, category, message, page=""):
    # Save a report from a signed-in student or professor and return its ID.
    if category not in CATEGORIES:
        raise ValueError("Choose a report type.")
    message = (message or "").strip()
    if len(message) < MIN_MESSAGE:
        raise ValueError(f"Please describe the issue in at least {MIN_MESSAGE} characters.")
    if len(message) > MAX_MESSAGE:
        raise ValueError(f"Reports can be at most {MAX_MESSAGE} characters.")
    user_id = db._object_id(user_id, "user ID")
    role = (db.read_one("users", {"_id": user_id}) or {}).get("permissions")
    if role not in {"student", "professor"}:
        raise ValueError("Sign in to send a report.")

    now = datetime.now(timezone.utc)
    _check_rate_limit(user_id, now)

    class_ids = [row["class_id"] for row in db.find("students", {"user_id": user_id})] if role == "student" else []
    return db.insert_one("feedback", {
        "user_id": user_id,
        "role": role,
        "class_ids": class_ids,
        "category": category,
        "message": message,
        "page": str(page or "")[:MAX_PAGE],
        "status": "new",
        "note": "",
        "created_at": now,
        "updated_at": now,
        "resolved_at": None,
    })


def _taught_class_ids(professor_id):
    # Class IDs the professor teaches. Raises unless the caller is a professor.
    professor_id = db._object_id(professor_id, "professor ID")
    if (db.read_one("users", {"_id": professor_id}) or {}).get("permissions") != "professor":
        raise ValueError("A professor account is required.")
    return [row["_id"] for row in db.find("classes", {"instructor_id": professor_id})]


def _display_name(user):
    user = user or {}
    return " ".join(filter(None, [user.get("first_name"), user.get("last_name")])) or user.get("email") or "Unknown student"


def list_feedback_for_professor(professor_id, status=None, category=None, limit=LIST_LIMIT):
    # Newest-first reports from students in the professor's classes.
    taught = _taught_class_ids(professor_id)
    if not taught:
        return []
    match = {"class_ids": {"$in": taught}}
    if status is not None:
        if status not in STATUSES:
            raise ValueError("Unknown status.")
        match["status"] = status
    if category is not None:
        if category not in CATEGORIES:
            raise ValueError("Unknown report type.")
        match["category"] = category
    rows = db.aggregate("feedback", [
        {"$match": match},
        {"$sort": {"created_at": -1, "_id": -1}},
        {"$limit": limit},
        {"$lookup": {
            "from": "users",
            "localField": "user_id",
            "foreignField": "_id",
            "as": "user",
            "pipeline": [{"$project": {"first_name": 1, "last_name": 1, "email": 1}}],
        }},
        {"$set": {"user": {"$arrayElemAt": ["$user", 0]}}},
    ])
    names = {row["_id"]: row.get("name", "Untitled class")
             for row in db.find("classes", {"_id": {"$in": taught}})}
    return [{
        "_id": row["_id"],
        "category": row.get("category"),
        "message": row.get("message", ""),
        "page": row.get("page", ""),
        "status": row.get("status", "new"),
        "note": row.get("note", ""),
        "created_at": row.get("created_at"),
        "student": _display_name(row.get("user")),
        # Only the professor's own classes are shown, never the student's other courses.
        "classes": [names[class_id] for class_id in row.get("class_ids", []) if class_id in names],
    } for row in rows]


def update_feedback_as(feedback_id, professor_id, status, note=""):
    # Change a report's status and private note, if it came from one of the professor's classes.
    if status not in STATUSES:
        raise ValueError("Unknown status.")
    note = (note or "").strip()
    if len(note) > MAX_NOTE:
        raise ValueError(f"Notes can be at most {MAX_NOTE} characters.")
    feedback_id = db._object_id(feedback_id, "feedback ID")
    taught = _taught_class_ids(professor_id)
    report = db.read_one("feedback", {"_id": feedback_id})
    if report is None:
        raise ValueError("That report no longer exists.")
    if not set(report.get("class_ids", [])) & set(taught):
        raise ValueError("You can only manage reports from your own classes.")
    now = datetime.now(timezone.utc)
    return db.update_one("feedback", {"_id": feedback_id}, {
        "status": status,
        "note": note,
        "updated_at": now,
        "resolved_at": now if status == "resolved" else None,
    })