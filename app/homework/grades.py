"""Tentative Rocky scores and confirmed assignment grades, without double counting."""

from datetime import datetime, timezone
from decimal import Decimal
from math import isfinite


def confirmed_grade(submission):
    """Professor overrides and explicit acceptance are both confirmed decisions."""
    if submission.get("grading_status") != "graded":
        return None
    return submission.get("professor_grade") or None


def effective_grade(submission):
    if submission.get("grading_status") != "graded":
        return None
    return confirmed_grade(submission) or submission.get("grading_result")


def _points(result):
    if not isinstance(result, dict):
        return None
    earned, possible = result.get("total_points"), result.get("max_points")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value)
           for value in (earned, possible)) or not 0 <= earned <= possible or possible <= 0:
        return None
    return Decimal(str(earned)), Decimal(str(possible))


def _time(value):
    if not isinstance(value, datetime):
        return datetime.min.replace(tzinfo=timezone.utc)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def course_score_summary(submissions):
    """One score per assignment: latest professor decision, otherwise latest AI grade.

    A newer tentative resubmission does not replace or add to a confirmed grade.
    Processing/failed work never contributes a fabricated zero or denominator.
    Caller must scope submissions to the authenticated student and course.
    """
    assignments = {}
    for submission in submissions:
        if submission.get("assignment_id") is not None:
            assignments.setdefault(submission["assignment_id"], []).append(submission)
    totals = {name: [Decimal(0), Decimal(0), 0] for name in ("confirmed", "tentative")}
    for attempts in assignments.values():
        confirmed = [row for row in attempts if _points(confirmed_grade(row)) is not None]
        if confirmed:
            chosen = max(confirmed, key=lambda row: (
                _time(row["professor_grade"].get("graded_at", row.get("submitted_at"))),
                _time(row.get("submitted_at")), str(row.get("_id", "")),
            ))
            category, result = "confirmed", confirmed_grade(chosen)
        else:
            tentative = [row for row in attempts if row.get("grading_status") == "graded"
                         and _points(row.get("grading_result")) is not None]
            if not tentative:
                continue
            chosen = max(tentative, key=lambda row: (_time(row.get("submitted_at")), str(row.get("_id", ""))))
            category, result = "tentative", chosen["grading_result"]
        earned, possible = _points(result)
        totals[category][0] += earned
        totals[category][1] += possible
        totals[category][2] += 1
    totals["combined"] = [sum(totals[name][i] for name in ("confirmed", "tentative")) for i in range(3)]
    return {name: {
        "earned": float(earned), "possible": float(possible), "assignments": count,
        "percentage": float(round(100 * earned / possible, 2)) if possible else None,
    } for name, (earned, possible, count) in totals.items()}
