#Database functions for homework assignments

from db.crud import create_one, read_many, read_one


#Create an empty homework assignment and return its MongoDB ID
def create_assignment(
    title: str,
    professor_id: str,
    description: str = "",
):
    title = title.strip()
    if not title:
        raise ValueError("Assignment title is required.")

    if not professor_id:
        raise ValueError("Professor ID is required.")

    assignment = {
        "title": title,
        "description": description.strip(),
        "professor_id": professor_id,
        "problems": [],
        "status": "draft",
    }

    return create_one("assignments", assignment)


#Return one assignment by its MongoDB ID
def get_assignment(assignment_id):
    if not assignment_id:
        raise ValueError("Assignment ID is required.")

    return read_one("assignments", {"_id": assignment_id})

#Return all assignments created by one professor
def list_assignments_for_professor(professor_id: str):
    if not professor_id:
        raise ValueError("Professor ID is required.")

    return read_many("assignments", {"professor_id": professor_id})
