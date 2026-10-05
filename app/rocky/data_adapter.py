"""Data adapter bridging MongoDB completed assignments and assignments
into the standardized (attempts, questions) schema expected by the recommendation analyzer.
"""
import math
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
from bson import ObjectId

# topic keyword patterns for discrete mathematics and logic
TOPIC_KEYWORD_PATTERNS = [
    (
        "Predicate Logic",
        [
            r"predicate",
            r"first[- ]order logic",
            r"quantifier",
            r"variable binding",
            r"domain of discourse",
            r"free variable",
            r"bound variable",
        ],
    ),
    (
        "Propositional Logic",
        [
            r"propositional",
            r"truth table",
            r"tautology",
            r"logical equivalence",
            r"modus ponens",
            r"boolean",
            r"connective",
            r"conjunction",
            r"disjunction",
            r"implication",
        ],
    ),
    (
        "Set Theory",
        [
            r"set theory",
            r"\bset\b",
            r"subset",
            r"power set",
            r"cartesian product",
            r"union",
            r"intersection",
            r"complement",
            r"venn diagram",
        ],
    ),
    (
        "Mathematical Induction",
        [
            r"induction",
            r"inductive",
            r"base case",
            r"inductive hypothesis",
            r"inductive step",
            r"well[- ]ordering",
        ],
    ),
    (
        "Relations & Functions",
        [
            r"equivalence relation",
            r"partial order",
            r"reflexive",
            r"symmetric",
            r"transitive",
            r"antisymmetric",
            r"bijection",
            r"injective",
            r"surjective",
            r"relation",
            r"function",
        ],
    ),
    (
        "Proof Techniques",
        [
            r"direct proof",
            r"contradiction",
            r"contraposition",
            r"contrapositive",
            r"proof by cases",
            r"counterexample",
        ],
    ),
    (
        "Combinatorics & Counting",
        [
            r"combinatorics",
            r"permutation",
            r"combination",
            r"pigeonhole",
            r"binomial coefficient",
            r"counting",
        ],
    ),
    (
        "Graph Theory",
        [
            r"graph",
            r"tree",
            r"vertex",
            r"vertices",
            r"edge",
            r"eulerian",
            r"hamiltonian",
            r"bipartite",
        ],
    ),
]


def infer_topic_from_text(
    title: str = "",
    description: str = "",
    content: str = "",
    explicit_topic: Optional[str] = None,
) -> str:
    """
    Determines the logic/math topic from explicit metadata or text keywords.
    """
    if explicit_topic and explicit_topic.strip():
        return explicit_topic.strip()

    combined_text = f"{title} {description} {content}".lower()

    for topic_name, patterns in TOPIC_KEYWORD_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                return topic_name

    # fallback to general category if text contains 'logic'
    if "logic" in combined_text:
        return "Propositional Logic"

    return "General Discrete Mathematics"


def normalize_score_ratio(score: float, total_possible: Optional[float] = None) -> float:
    """
    Normalizes a numeric score to an accuracy ratio between 0.0 and 1.0.
    """
    if not math.isfinite(score) or score <= 0:
        return 0.0

    if total_possible and total_possible > 0:
        return min(max(score / total_possible, 0.0), 1.0)

    # Heuristic when total_possible is not specified:
    # If score <= 1.0, it is already a ratio (e.g. 0.85 = 85%)
    if score <= 1.0:
        return score

    # If score <= 10.0, assume a 10-point scale
    if score <= 10.0:
        return min(score / 10.0, 1.0)

    # If score <= 100.0, assume a 100-point scale
    if score <= 100.0:
        return min(score / 100.0, 1.0)

    # For larger values, cap at 1.0
    return 1.0


def build_attempts_and_questions_from_completions(
    completions: List[Dict[str, Any]],
    assignments_map: Dict[str, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Converts MongoDB completed_assignments and assignments into (attempts, questions)
    expected by the analyzer.
    """
    attempts: List[Dict[str, Any]] = []
    questions_dict: Dict[str, Dict[str, Any]] = {}

    for comp_idx, completion in enumerate(completions):
        assignment_id_raw = completion.get("assignment_id")
        if not assignment_id_raw:
            continue
        assignment_id = str(assignment_id_raw)
        assignment = assignments_map.get(assignment_id)
        if not assignment:
            continue

        # Completion records contain total points, not individual problem grades.
        # Keep one numeric observation per completion; never invent which
        # problems were correct from their position in the assignment.
        raw_score = completion.get("score")
        if isinstance(raw_score, bool):
            continue
        try:
            raw_score = float(raw_score)
        except (TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(raw_score) or raw_score < 0:
            continue

        problems = [
            {"content": problem} if isinstance(problem, str) else problem
            for problem in assignment.get("problems", [])
        ]
        total_possible = assignment.get("max_score") or assignment.get("total_points")
        if total_possible is None and problems:
            total_possible = sum(problem.get("points", 1.0) for problem in problems)
        # Without a denominator there is no reliable way to infer a points scale.
        if (isinstance(total_possible, bool)
                or not isinstance(total_possible, (int, float))
                or not math.isfinite(total_possible) or total_possible <= 0):
            continue
        accuracy_ratio = normalize_score_ratio(raw_score, total_possible)

        title = assignment.get("title", "Assignment")
        description = assignment.get("description", "")
        problem_topics = {
            infer_topic_from_text(
                title=title, description=description,
                content=problem.get("content", ""),
                explicit_topic=problem.get("topic") or assignment.get("topic"),
            )
            for problem in problems
        }
        if len(problem_topics) > 1:
            # A total score cannot establish mastery of any component topic.
            topic = f"Mixed-topic assignment: {title} ({assignment_id})"
        elif problem_topics:
            topic = next(iter(problem_topics))
        else:
            topic = infer_topic_from_text(
                title=title, description=description,
                explicit_topic=assignment.get("topic"),
            )

        # IDs supplied by problems are assignment-local. Aggregate question IDs
        # are always namespaced, even when assignments reuse those problem IDs.
        question_id = f"{assignment_id}:overall"
        questions_dict[question_id] = {
            "_id": question_id,
            "assignment_id": assignment_id,
            "topic": topic,
            "performance_scope": "assignment",
        }
        attempts.append({
            "_id": f"comp_{comp_idx}",
            "student_id": str(completion.get("user_id", "anonymous")),
            "question_id": question_id,
            "accuracy": accuracy_ratio,
            "timestamp": completion.get("completed_at", datetime.now(timezone.utc)),
        })

    return attempts, list(questions_dict.values())


def get_student_performance_from_db(
    user_id: str | ObjectId,
    db_instance=None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Fetches a student's completion history from MongoDB and adapts it into (attempts, questions).
    """
    if db_instance is None:
        from db.DataBase import db
        db_instance = db

    user_obj_id = db_instance._object_id(user_id, "user ID")
    completions = list(db_instance.find("completed_assignments", {"user_id": user_obj_id}))
    if not completions:
        return [], []

    assignment_ids = list({c["assignment_id"] for c in completions if "assignment_id" in c})
    assignments = list(db_instance.find("assignments", {"_id": {"$in": assignment_ids}}))
    assignments_map = {str(a["_id"]): a for a in assignments}

    return build_attempts_and_questions_from_completions(completions, assignments_map)


def get_class_performance_from_db(
    class_id: str | ObjectId,
    db_instance=None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Fetches class-wide assignment completion history from MongoDB and adapts it into (attempts, questions).
    """
    if db_instance is None:
        from db.DataBase import db
        db_instance = db

    class_obj_id = db_instance._object_id(class_id, "class ID")
    assignments = list(db_instance.find("assignments", {"class_id": class_obj_id}))
    if not assignments:
        return [], []

    assignments_map = {str(a["_id"]): a for a in assignments}
    assignment_ids = list(assignments_map.keys())

    # Find all completions across all students for these assignments
    obj_ids = [db_instance._object_id(aid, "assignment ID") for aid in assignment_ids]
    completions = list(db_instance.find("completed_assignments", {"assignment_id": {"$in": obj_ids}}))

    return build_attempts_and_questions_from_completions(completions, assignments_map)

