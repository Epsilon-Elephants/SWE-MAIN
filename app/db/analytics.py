"""Batch analytics reads limited to the authenticated professor's classes."""

from collections import defaultdict

from db.DataBase import db
from homework.analytics import summarize_scores, valid_score


def load_professor_analytics(professor_id, class_ids=None):
    uid = db._object_id(professor_id, "professor ID")
    if db.read_one("users", {"_id": uid, "permissions": "professor"}) is None:
        raise ValueError("A professor account is required.")
    query = {"instructor_id": uid}
    if class_ids is not None:
        query["_id"] = {"$in": [db._object_id(cid, "class ID") for cid in class_ids]}
    courses = list(db.find("classes", query))
    ids = [row["_id"] for row in courses]
    if not ids:
        return {"classes": {}, "assignments": {}}
    # Fetch only the fields required for summaries. Answer keys and responses
    # never leave the database for this read.
    rows = list(db.aggregate("homework_submissions", [
        {"$match": {"class_id": {"$in": ids}, "grading_status": "graded"}},
        {"$sort": {"submitted_at": -1, "_id": -1}},
        {"$group": {"_id": {"student": "$user_id", "assignment": "$assignment_id"},
                     "attempt": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$attempt"}},
        {"$project": {"user_id": 1, "class_id": 1, "assignment_id": 1,
                      "submitted_at": 1, "grading_status": 1,
                      "grading_result.total_points": 1, "grading_result.max_points": 1,
                      "grading_result.problems.problem_id": 1,
                      "grading_result.problems.points_awarded": 1,
                      "grading_result.problems.max_points": 1,
                      "assignment_snapshot.problems.problem_id": 1,
                      "assignment_snapshot.problems.topic": 1}},
    ]))
    memberships = list(db.find("students", {"class_id": {"$in": ids}}))
    by_class, by_assignment, recorded_grades = defaultdict(list), defaultdict(list), defaultdict(list)
    for row in rows:
        by_class[row["class_id"]].append(row)
        by_assignment[row["assignment_id"]].append(row)
    for row in memberships:
        recorded_grades[row["class_id"]].append(row.get("grade") or {})
    classes = {}
    for cid in ids:
        summary = summarize_scores(by_class[cid])
        percentages = [grade["earned"] / grade["possible"] * 100 for grade in recorded_grades[cid]
                       if valid_score(grade.get("earned"), grade.get("possible"))]
        summary["recorded_average"] = sum(percentages) / len(percentages) if percentages else None
        summary["recorded_students"] = len(percentages)
        classes[cid] = summary
    return {"classes": classes, "assignments": {
        aid: summarize_scores(attempts) for aid, attempts in by_assignment.items()
    }}
