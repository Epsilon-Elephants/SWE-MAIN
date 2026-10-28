# Database functions for homework assignments

from datetime import date, datetime, time, timezone

from db.DataBase import db
from homework.schema import normalize_problem, normalize_problems


_UNSET = object()


def _utc_date(value, label):
    """Store BSON dates in UTC; naive datetimes and calendar dates mean UTC."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=timezone.utc)
    raise ValueError(f"{label} must be a date or datetime.")


def _schedule(posted, due_date):
    if posted is None:
        raise ValueError("Posted date is required.")
    if due_date is None:
        raise ValueError("Due date is required.")
    posted = _utc_date(posted, "Posted date")
    due_date = _utc_date(due_date, "Due date")
    if due_date < posted:
        raise ValueError("Due date cannot be before the posted date.")
    return {"posted": posted, "due_date": due_date}


def _schedule_update(query, posted, due_date, status):
    existing = db.read_one("assignments", query) or {}
    if status != "draft":
        _require_problems(existing.get("problems"))
    return _schedule(
        existing.get("posted") if posted is _UNSET else posted,
        existing.get("due_date") if due_date is _UNSET else due_date,
    )


def _require_problems(problems):
    if not problems:
        raise ValueError("At least one problem is required.")
    if any(not problem.get("content", "").strip() for problem in problems):
        raise ValueError("Problem content is required.")


def _student_visibility(now):
    # Closed/old homework remains available. Missing posted dates are legacy homework.
    return {
        "status": {"$in": ["published", "closed"]},
        "$or": [{"posted": {"$lte": now}}, {"posted": None}],
    }


def list_assignments_for_student(user_id):
    """Return posted homework in enrolled classes, including past-due homework."""
    if not user_id:
        raise ValueError("User ID is required.")
    user_id = db._object_id(user_id, "user ID")
    class_ids = [row["class_id"] for row in db.find("students", {"user_id": user_id})]
    if not class_ids:
        return []
    return list(db.find("assignments", {
        "class_id": {"$in": class_ids},
        **_student_visibility(datetime.now(timezone.utc)),
    }))


# Create a complete homework assignment and return its MongoDB ID
def create_assignment(
    title: str,
    professor_id: str,
    description: str = "",
    *,
    class_id,
    posted=None,
    due_date=None,
    problems=None,
    status="draft",
):
    title = title.strip()
    if not title:
        raise ValueError("Assignment title is required.")
    if not professor_id:
        raise ValueError("Professor ID is required.")
    if not class_id:
        raise ValueError("Class ID is required.")
    if status not in ("draft", "published", "closed"):
        raise ValueError("Assignment status must be draft, published, or closed.")
    class_id = db._object_id(class_id, "class ID")
    instructor_id = db._object_id(professor_id, "professor ID")
    if db.read_one("classes", {"_id": class_id, "instructor_id": instructor_id}) is None:
        raise ValueError("Select a class that you teach.")

    problem_documents = [] if status == "draft" and not problems else normalize_problems(problems)

    assignment = {
        "title": title,
        "description": description.strip(),
        "professor_id": professor_id,
        "class_id": class_id,
        "problems": problem_documents,
        "status": status,
        **_schedule(posted, due_date),
    }

    return db.insert_one("assignments", assignment)


# Return one assignment by its MongoDB ID
def get_assignment(assignment_id):
    if not assignment_id:
        raise ValueError("Assignment ID is required.")

    return db.read_one("assignments", {"_id": db._object_id(assignment_id, "assignment ID")})


# Return all assignments created by one professor
def list_assignments_for_professor(professor_id: str):
    if not professor_id:
        raise ValueError("Professor ID is required.")

    return list(db.find("assignments", {"professor_id": professor_id}))




# Update an assignment that belongs to a professor
def update_assignment(
    assignment_id,
    professor_id: str,
    title: str,
    description: str = "",
    status: str = "draft",
    *,
    posted=_UNSET,
    due_date=_UNSET,
):
    if not assignment_id:
        raise ValueError("Assignment ID is required.")
    if not professor_id:
        raise ValueError("Professor ID is required.")
    title = title.strip()
    if not title:
        raise ValueError("Assignment title is required.")
    if status not in ("draft", "published", "closed"):
        raise ValueError("Assignment status must be draft, published, or closed.")

    fields = {
        "title": title,
        "description": description.strip(),
        "status": status,
        **_schedule_update(
            {"_id": assignment_id, "professor_id": professor_id}, posted, due_date, status,
        ),
    }

    result = db.update_one(
        "assignments",
        {"_id": assignment_id, "professor_id": professor_id},
        fields,
    )
    return result.matched_count > 0


def set_assignment_status(assignment_id, professor_id: str, status: str):
    """Close or reopen a professor's assignment without touching its content.

    Publishing re-validates problems and dates so an incomplete assignment can't go live.
    """
    if not assignment_id:
        raise ValueError("Assignment ID is required.")
    if not professor_id:
        raise ValueError("Professor ID is required.")
    if status not in ("draft", "published", "closed"):
        raise ValueError("Assignment status must be draft, published, or closed.")
    query = {"_id": assignment_id, "professor_id": professor_id}
    fields = {"status": status}
    if status == "published":
        fields.update(_schedule_update(query, _UNSET, _UNSET, status))
    result = db.update_one("assignments", query, fields)
    return result.matched_count > 0


# Delete an assignment that belongs to a professor
def delete_assignment(assignment_id, professor_id: str):
    if not assignment_id:
        raise ValueError("Assignment ID is required.")
    if not professor_id:
        raise ValueError("Professor ID is required.")

    result = db.delete_one(
        "assignments",
        {"_id": assignment_id, "professor_id": professor_id},
    )
    return result.deleted_count > 0


# add a problem to an assignment and return the new problem ID
def add_problem(assignment_id, professor_id: str, content: str | dict):
    if not assignment_id:
        raise ValueError("Assignment ID is required.")
    if not professor_id:
        raise ValueError("Professor ID is required.")

    problem = normalize_problem(content)

    query = {"_id": assignment_id, "professor_id": professor_id}
    assignment = db.read_one("assignments", query)
    if assignment is None:
        return None

    problems = list(assignment.get("problems", []))
    problems.append(problem)

    result = db.update_one("assignments", query, {"problems": problems})
    if result.matched_count == 0:
        return None

    return problem["problem_id"]


# Update one problem in an assignment
def update_problem(
    assignment_id,
    professor_id: str,
    problem_id: str,
    content: str | dict,
):
    if not assignment_id:
        raise ValueError("Assignment ID is required.")
    if not professor_id:
        raise ValueError("Professor ID is required.")
    if not problem_id:
        raise ValueError("Problem ID is required.")

    if isinstance(content, str) and not content.strip():
        raise ValueError("Problem content is required.")

    query = {"_id": assignment_id, "professor_id": professor_id}
    assignment = db.read_one("assignments", query)
    if assignment is None:
        return False

    problems = [dict(problem) for problem in assignment.get("problems", [])]
    for problem in problems:
        if problem.get("problem_id") == problem_id:
            source = {**problem, "content": content} if isinstance(content, str) else content
            problem.update(normalize_problem(source, problem_id=problem_id))
            result = db.update_one("assignments", query, {"problems": problems})
            return result.matched_count > 0

    return False


# Delete one problem from an assignment
def delete_problem(assignment_id, professor_id: str, problem_id: str):
    if not assignment_id:
        raise ValueError("Assignment ID is required.")
    if not professor_id:
        raise ValueError("Professor ID is required.")
    if not problem_id:
        raise ValueError("Problem ID is required.")

    query = {"_id": assignment_id, "professor_id": professor_id}
    assignment = db.read_one("assignments", query)
    if assignment is None:
        return False

    current_problems = assignment.get("problems", [])
    problems = [
        problem
        for problem in current_problems
        if problem.get("problem_id") != problem_id
    ]
    if len(problems) == len(current_problems):
        return False

    _require_problems(problems)

    result = db.update_one("assignments", query, {"problems": problems})
    return result.matched_count > 0
