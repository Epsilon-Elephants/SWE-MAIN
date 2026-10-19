# Database functions for homework assignments

from uuid import uuid4

from db.DataBase import db


# Create an empty homework assignment and return its MongoDB ID
def create_assignment(
    title: str,
    professor_id: str,
    description: str = "",
    *,
    class_id,
):
    title = title.strip()
    if not title:
        raise ValueError("Assignment title is required.")
    if not professor_id:
        raise ValueError("Professor ID is required.")
    if not class_id:
        raise ValueError("Class ID is required.")
    class_id = db._object_id(class_id, "class ID")
    instructor_id = db._object_id(professor_id, "professor ID")
    if db.read_one("classes", {"_id": class_id, "instructor_id": instructor_id}) is None:
        raise ValueError("Select a class that you teach.")

    assignment = {
        "title": title,
        "description": description.strip(),
        "professor_id": professor_id,
        "class_id": class_id,
        "problems": [],
        "status": "draft",
    }

    return db.insert_one("assignments", assignment)


# Return one assignment by its MongoDB ID
def get_assignment(assignment_id):
    if not assignment_id:
        raise ValueError("Assignment ID is required.")

    return db.read_one("assignments", {"_id": assignment_id})


# Return all assignments created by one professor
def list_assignments_for_professor(professor_id: str):
    if not professor_id:
        raise ValueError("Professor ID is required.")

    return list(db.find("assignments", {"professor_id": professor_id}))


def list_assignments_for_class(class_id):
    """Return homework linked to a class, accepting an ObjectId or its string form."""
    if not class_id:
        raise ValueError("Class ID is required.")
    class_id = db._object_id(class_id, "class ID")
    return list(db.find("assignments", {"class_id": class_id}))


# Update an assignment that belongs to a professor
def update_assignment(
    assignment_id,
    professor_id: str,
    title: str,
    description: str = "",
    status: str = "draft",
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
    }

    result = db.update_one(
        "assignments",
        {"_id": assignment_id, "professor_id": professor_id},
        fields,
    )
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
def add_problem(assignment_id, professor_id: str, content: str):
    if not assignment_id:
        raise ValueError("Assignment ID is required.")
    if not professor_id:
        raise ValueError("Professor ID is required.")

    content = content.strip()
    if not content:
        raise ValueError("Problem content is required.")

    query = {"_id": assignment_id, "professor_id": professor_id}
    assignment = db.read_one("assignments", query)
    if assignment is None:
        return None

    problem = {
        "problem_id": str(uuid4()),
        "content": content,
    }
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
    content: str,
):
    if not assignment_id:
        raise ValueError("Assignment ID is required.")
    if not professor_id:
        raise ValueError("Professor ID is required.")
    if not problem_id:
        raise ValueError("Problem ID is required.")

    content = content.strip()
    if not content:
        raise ValueError("Problem content is required.")

    query = {"_id": assignment_id, "professor_id": professor_id}
    assignment = db.read_one("assignments", query)
    if assignment is None:
        return False

    problems = [dict(problem) for problem in assignment.get("problems", [])]
    for problem in problems:
        if problem.get("problem_id") == problem_id:
            problem["content"] = content
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

    result = db.update_one("assignments", query, {"problems": problems})
    return result.matched_count > 0
