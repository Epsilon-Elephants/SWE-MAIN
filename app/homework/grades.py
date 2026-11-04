"""Choose the published grade without changing Rocky's original result."""


def effective_grade(submission):
    if submission.get("grading_status") != "graded":
        return None
    return submission.get("professor_grade") or submission.get("grading_result")
