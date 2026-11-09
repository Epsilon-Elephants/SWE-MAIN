"""Student-safe practice guidance grounded in saved topic labels and scores."""

from homework.grades import effective_grade


def practice_suggestion(problem, points_awarded):
    topic = problem.get("topic", "").strip()
    name = (topic[:120] + "…" if len(topic) > 120 else topic) or "this question's topic"
    normalized = topic.casefold()
    if any(word in normalized for word in ("quantifier", "predicate")):
        practice = "Translate two statements into predicate logic, negate each one, and check how the quantifiers change."
    elif any(word in normalized for word in ("proposition", "conjunction", "disjunction", "truth table")):
        practice = "Build truth tables for two new compound statements and explain which truth-value assignments make them true."
    elif "set" in normalized:
        practice = "Choose two small sets and work out their union, intersection, and difference, explaining each element's membership."
    elif "induction" in normalized:
        practice = "Practice one new induction proof, stating the base case, induction hypothesis, and the step that uses it."
    elif any(word in normalized for word in ("relation", "function")):
        practice = "Construct a small example and a counterexample for each property of a relation or function you are studying."
    elif any(word in normalized for word in ("graph", "tree")):
        practice = "Draw two small graphs and compare their paths, cycles, and vertex degrees, explaining each conclusion."
    else:
        practice = f"Review the core definitions of {name}, then solve two new examples and explain each step in your own words."
    if points_awarded >= problem.get("points", 1):
        return f"Extend your work on {name}: {practice} Try a harder variation and explain why the same method applies."
    return f"Focus your next practice on {name}: {practice} Use the grading feedback to check the step you found difficult."


def submission_recommendations(submissions):
    """Latest graded attempt per assignment; prioritize the weakest listed topics."""
    topics, assignments = {}, set()
    for submission in sorted(submissions, key=lambda row: row["submitted_at"], reverse=True):
        grade = effective_grade(submission)
        if not grade or submission["assignment_id"] in assignments:
            continue
        assignments.add(submission["assignment_id"])
        by_id = {row["problem_id"]: row for row in grade.get("problems", [])}
        for problem in submission["assignment_snapshot"]["problems"]:
            result = by_id.get(problem["problem_id"])
            if not result:
                continue
            topic = problem.get("topic", "").strip()
            if not topic:
                continue
            ratio = result["points_awarded"] / problem["points"]
            current = topics.get(topic)
            if current is None or ratio < current["ratio"]:
                topics[topic] = {
                    "topic": topic, "ratio": ratio,
                    "recommendation": result.get("study_recommendation") or practice_suggestion(problem, result["points_awarded"]),
                    "assignment_id": str(submission["assignment_id"]),
                }
    return sorted(topics.values(), key=lambda row: (row["ratio"], row["topic"].casefold()))
