"""Score and topic summaries from saved grades, without exposing answer keys."""

from collections import defaultdict
from datetime import datetime, timezone
from math import isfinite

STRUGGLE_THRESHOLD = 70


def valid_score(earned, possible):
    return (all(isinstance(value, (int, float)) and not isinstance(value, bool)
                and isfinite(value) for value in (earned, possible))
            and possible > 0 and 0 <= earned <= possible)


def _attempt_order(row):
    submitted = row.get("submitted_at")
    if not isinstance(submitted, datetime):
        submitted = datetime.min.replace(tzinfo=timezone.utc)
    elif submitted.tzinfo is None:
        submitted = submitted.replace(tzinfo=timezone.utc)
    return submitted, str(row.get("_id", ""))


def latest_graded_attempts(rows):
    """Pending/failed retries keep the last graded result until they are graded."""
    latest = {}
    for row in sorted(rows, key=_attempt_order, reverse=True):
        result = row.get("grading_result") or {}
        if (row.get("grading_status") == "graded" and row.get("user_id") is not None
                and row.get("assignment_id") is not None
                and valid_score(result.get("total_points"), result.get("max_points"))):
            latest.setdefault((row["user_id"], row["assignment_id"]), row)
    return list(latest.values())


def summarize_scores(rows):
    """Average student percentages; weight assignments by points within each student.

    Topics use the saved problem labels. A topic is flagged for a student when
    their combined score for its questions is below 70%, using latest grades.
    """
    rows = latest_graded_attempts(rows)
    students = defaultdict(lambda: [0, 0])
    topics = {}
    for row in rows:
        result = row["grading_result"]
        total = students[row["user_id"]]
        total[0] += result["total_points"]
        total[1] += result["max_points"]
        problems = {problem.get("problem_id"): problem for problem in
                    (row.get("assignment_snapshot") or {}).get("problems", [])}
        for grade in result.get("problems", []):
            problem = problems.get(grade.get("problem_id"), {})
            label = (problem.get("topic") or "").strip()
            earned, possible = grade.get("points_awarded"), grade.get("max_points")
            if not label or not valid_score(earned, possible):
                continue
            topic = topics.setdefault(label.casefold(), {"topic": label, "students": defaultdict(lambda: [0, 0])})
            score = topic["students"][row["user_id"]]
            score[0] += earned
            score[1] += possible
    struggling = []
    for topic in topics.values():
        percentages = [earned / possible * 100 for earned, possible in topic["students"].values()]
        count = sum(value < STRUGGLE_THRESHOLD for value in percentages)
        if count:
            struggling.append({"topic": topic["topic"], "struggling_students": count,
                               "students": len(percentages), "average": sum(percentages) / len(percentages)})
    struggling.sort(key=lambda topic: (-topic["struggling_students"], topic["average"], topic["topic"].casefold()))
    percentages = [earned / possible * 100 for earned, possible in students.values()]
    return {"average": sum(percentages) / len(percentages) if percentages else None,
            "graded_students": len(students), "graded_assignments": len(rows),
            "has_topics": bool(topics), "struggling_topics": struggling}
