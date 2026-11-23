"""Score and topic summaries from saved grades, without exposing answer keys."""

from collections import defaultdict
from math import isfinite
from homework.grades import attempt_score, confirmed_grade, kept_attempt

STRUGGLE_THRESHOLD = 70


def valid_score(earned, possible):
    return (all(isinstance(value, (int, float)) and not isinstance(value, bool)
                and isfinite(value) for value in (earned, possible))
            and possible > 0 and 0 <= earned <= possible)


def kept_graded_attempts(rows):
    """One counted attempt per (student, assignment), chosen exactly as course totals do."""
    groups = {}
    for row in rows:
        if row.get("user_id") is not None and row.get("assignment_id") is not None:
            groups.setdefault((row["user_id"], row["assignment_id"]), []).append(row)
    kept = (kept_attempt(attempts) for attempts in groups.values())
    return [row for row in kept if row is not None]


def summarize_scores(rows):
    """Average student percentages; weight assignments by points within each student.

    Topics use the saved problem labels. A topic is flagged for a student when
    their combined score for its questions is below 70%, using each kept grade
    (professor decision, otherwise the student's highest Rocky attempt).
    """
    rows = kept_graded_attempts(rows)
    students = defaultdict(lambda: [0, 0])
    topics = {}
    for row in rows:
        result = confirmed_grade(row) if attempt_score(row)[2] else row["grading_result"]
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
