"""Versioned short-answer contract shared by authoring, submission, and future grading."""

from math import isfinite
from uuid import uuid4

SCHEMA_VERSION = 1


def normalize_problem(value, *, problem_id=None):
    """Upgrade legacy strings/documents without changing existing problem IDs.

    Grading guidance is instructor-only. Never send the whole document to a
    student widget or include it in a student-facing JSON download.
    """
    if not isinstance(value, (str, dict)):
        raise ValueError("Problem must be text or a structured problem document.")
    source = {"content": value} if isinstance(value, str) else dict(value)
    version = source.get("schema_version", SCHEMA_VERSION)
    if type(version) is not int or version != SCHEMA_VERSION:
        raise ValueError("Unsupported problem schema version.")
    content = source.get("content", "")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Problem content is required.")
    if source.get("type", "short_answer") != "short_answer":
        raise ValueError("Only short-answer problems are supported.")
    points = source.get("points", 1.0)
    if isinstance(points, bool) or not isinstance(points, (int, float)) or not isfinite(points) or points <= 0:
        raise ValueError("Problem points must be a finite, positive number.")
    fields = {}
    for key in ("topic", "reference_answer", "grading_guidance"):
        text = source.get(key, "")
        if not isinstance(text, str):
            raise ValueError(f"Problem {key} must be text.")
        fields[key] = text.strip()
    identifier = problem_id if problem_id is not None else source.get("problem_id")
    if identifier is None:
        identifier = str(uuid4())
    if not isinstance(identifier, str) or not identifier.strip():
        raise ValueError("Problem ID must be nonblank text.")
    return {
        "schema_version": SCHEMA_VERSION,
        "problem_id": identifier,
        "type": "short_answer",
        "content": content.strip(),
        "points": float(points),
        **fields,
    }


def normalize_problems(problems):
    if not problems:
        raise ValueError("At least one problem is required.")
    normalized = [normalize_problem(problem) for problem in problems]
    ids = [problem["problem_id"] for problem in normalized]
    if len(set(ids)) != len(ids):
        raise ValueError("Problem IDs must be unique within an assignment.")
    return normalized


def build_grading_payload(submission):
    """Build JSON-safe input for future Rocky integration; does not call any AI.

    Trusted server use only: this includes private instructor grading guidance.
    Student answers are untrusted content, never model instructions.
    """
    if submission.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported submission schema version.")
    answers = {answer["problem_id"]: answer["answer"] for answer in submission["answers"]}
    return {
        "schema_version": SCHEMA_VERSION,
        "submission_id": str(submission["_id"]),
        "assignment_id": str(submission["assignment_id"]),
        "assignment_title": submission["assignment_snapshot"]["title"],
        "assignment_description": submission["assignment_snapshot"]["description"],
        "problems": [
            {**problem, "student_answer": answers[problem["problem_id"]]}
            for problem in submission["assignment_snapshot"]["problems"]
        ],
    }
