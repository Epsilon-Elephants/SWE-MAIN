"""Tests for the recommendation data adapter bridging MongoDB completions and assignments.

Follows the reference testing pattern:
    Run without Python's -O option so assertions execute:
    python tests/test_data_adapter.py
"""
from datetime import datetime
import pytest
from bson import ObjectId

from app.rocky.analyzer import analyze_student_weaknesses, analyze_class_weaknesses

from app.rocky.data_adapter import (
    infer_topic_from_text,
    normalize_score_ratio,
    build_attempts_and_questions_from_completions,
    get_student_performance_from_db,
    get_class_performance_from_db,
)


def test_infer_topic_from_text():
    # Explicit topic takes priority
    assert infer_topic_from_text(explicit_topic="Set Theory") == "Set Theory"
    assert infer_topic_from_text(title="Truth Tables", explicit_topic="Predicate Logic") == "Predicate Logic"

    # Inferred from title or description
    assert infer_topic_from_text(title="Homework 1: Propositional Logic") == "Propositional Logic"
    assert infer_topic_from_text(title="Quiz 2", description="Translating with universal quantifiers") == "Predicate Logic"
    assert infer_topic_from_text(title="Assignment 3", content="Prove by mathematical induction") == "Mathematical Induction"
    assert infer_topic_from_text(title="Subsets and Power Sets") == "Set Theory"
    assert infer_topic_from_text(title="Equivalence Relations and Injective Functions") == "Relations & Functions"
    assert infer_topic_from_text(title="Proof by Contradiction") == "Proof Techniques"

    # Fallback
    assert infer_topic_from_text(title="Final Comprehensive Exam") == "General Discrete Mathematics"


def test_normalize_score_ratio():
    # Fractional ratio (0.0 to 1.0)
    assert normalize_score_ratio(0.85) == 0.85
    assert normalize_score_ratio(1.0) == 1.0
    assert normalize_score_ratio(0.0) == 0.0
    assert normalize_score_ratio(-5.0) == 0.0

    # 10-point scale
    assert normalize_score_ratio(8.0) == 0.8
    assert normalize_score_ratio(10.0) == 1.0

    # 100-point scale
    assert normalize_score_ratio(75.0) == 0.75
    assert normalize_score_ratio(100.0) == 1.0

    # Explicit total possible
    assert normalize_score_ratio(15.0, total_possible=20.0) == 0.75
    assert normalize_score_ratio(50.0, total_possible=50.0) == 1.0


def test_build_attempts_and_questions():
    asgt_id = str(ObjectId())
    assignments_map = {
        asgt_id: {
            "_id": asgt_id,
            "title": "Predicate Logic Homework",
            "description": "Quantifiers and domain of discourse",
            "problems": [
                {"problem_id": "p1", "content": "Translate: All humans are mortal."},
                {"problem_id": "p2", "content": "Translate: Some students like logic."},
                {"problem_id": "p3", "content": "Find free variables in P(x, y)."},
                {"problem_id": "p4", "content": "Prove validity using quantifiers."},
            ],
            "total_points": 40.0,
        }
    }

    # Student scored 20/40. Individual problem grades are unknown.
    completions = [
        {
            "_id": ObjectId(),
            "assignment_id": asgt_id,
            "user_id": "student_1",
            "score": 20.0,
            "completed_at": datetime.now(),
        }
    ]

    attempts, questions = build_attempts_and_questions_from_completions(completions, assignments_map)

    assert len(questions) == 1
    assert questions[0]["topic"] == "Predicate Logic"
    assert questions[0]["performance_scope"] == "assignment"
    assert len(attempts) == 1
    assert attempts[0]["accuracy"] == 0.5
    assert "correct" not in attempts[0]


def test_mock_db_retrieval_student():
    student_id = ObjectId()
    asgt_id = ObjectId()

    mock_completions = [
        {
            "_id": ObjectId(),
            "assignment_id": asgt_id,
            "user_id": student_id,
            "score": 8.0,
            "completed_at": datetime.now(),
        }
    ]
    mock_assignments = [
        {
            "_id": asgt_id,
            "title": "Set Theory Practice",
            "problems": [
                {"problem_id": "p1", "content": "Find the power set of {1, 2}."},
            ],
            "total_points": 10.0,
        }
    ]

    class MockDB:
        def _object_id(self, val, label=""):
            return val if isinstance(val, ObjectId) else ObjectId(val)

        def find(self, collection_name, query):
            if collection_name == "completed_assignments":
                return mock_completions
            if collection_name == "assignments":
                return mock_assignments
            return []

    attempts, questions = get_student_performance_from_db(student_id, db_instance=MockDB())
    assert len(questions) == 1
    assert questions[0]["topic"] == "Set Theory"
    assert len(attempts) == 1
    assert attempts[0]["accuracy"] == 0.8


def test_mock_db_retrieval_class():
    class_id = ObjectId()
    asgt_id = ObjectId()

    mock_assignments = [
        {
            "_id": asgt_id,
            "class_id": class_id,
            "title": "Induction Basics",
            "problems": [
                {"problem_id": "p1", "content": "Base case step."},
                {"problem_id": "p2", "content": "Inductive hypothesis."},
            ],
            "total_points": 20.0,
        }
    ]
    mock_completions = [
        {"_id": ObjectId(), "assignment_id": asgt_id, "user_id": "s1", "score": 20.0},
        {"_id": ObjectId(), "assignment_id": asgt_id, "user_id": "s2", "score": 0.0},
    ]

    class MockDB:
        def _object_id(self, val, label=""):
            return val if isinstance(val, ObjectId) else ObjectId(val)

        def find(self, collection_name, query):
            if collection_name == "assignments":
                return mock_assignments
            if collection_name == "completed_assignments":
                return mock_completions
            return []

    attempts, questions = get_class_performance_from_db(class_id, db_instance=MockDB())
    assert len(questions) == 1
    assert questions[0]["topic"] == "Mathematical Induction"
    assert len(attempts) == 2  # One total score per student
    assert analyze_class_weaknesses(attempts, questions)[0]["accuracy"] == 0.5


def main():
    test_infer_topic_from_text()
    test_normalize_score_ratio()
    test_build_attempts_and_questions()
    test_mock_db_retrieval_student()
    test_mock_db_retrieval_class()
    print("All data adapter tests passed.")


if __name__ == "__main__":
    main()



@pytest.mark.parametrize("problems,score,expected", [
    ([{"content": "Truth tables"}], 1, 1.0),
    ([{"content": "Truth tables", "points": 2}, {"content": "Tautology", "points": 6}], 6, 0.75),
    (["Truth tables", "Tautology"], 1, 0.5),
    (["Truth tables"], 0, 0.0),
])
def test_stored_problem_points_and_legacy_strings(problems, score, expected):
    attempts, questions = build_attempts_and_questions_from_completions(
        [{"assignment_id": "a1", "score": score}],
        {"a1": {"problems": problems}},
    )
    assert attempts[0]["accuracy"] == expected
    assert analyze_student_weaknesses(attempts, questions)[0]["accuracy"] == expected


def test_reused_problem_ids_do_not_mix_assignments_or_topics():
    assignments = {
        "a1": {"problems": [{"problem_id": "p1", "content": "Quantifiers", "topic": "Predicate Logic"}]},
        "a2": {"problems": [{"problem_id": "p1", "content": "Power set", "topic": "Set Theory"}]},
    }
    attempts, questions = build_attempts_and_questions_from_completions(
        [{"assignment_id": "a1", "score": 1}, {"assignment_id": "a2", "score": 0}], assignments,
    )
    assert len({q["_id"] for q in questions}) == 2
    assert {q["assignment_id"] for q in questions} == {"a1", "a2"}
    assert {r["topic"]: r["accuracy"] for r in analyze_student_weaknesses(attempts, questions)} == {
        "Predicate Logic": 1.0, "Set Theory": 0.0,
    }


def test_mixed_topic_assignment_score_does_not_invent_problem_grades():
    problems = [
        {"problem_id": "p1", "content": "Quantifiers", "topic": "Predicate Logic"},
        {"problem_id": "p2", "content": "Power set", "topic": "Set Theory"},
    ]
    def adapt(items):
        return build_attempts_and_questions_from_completions(
            [{"assignment_id": "a1", "score": 1}],
            {"a1": {"title": "Review", "problems": items}},
        )
    attempts, questions = adapt(problems)
    # Timestamps may differ; metrics and attribution must not depend on ordering.
    assert analyze_student_weaknesses(*adapt(list(reversed(problems)))) == analyze_student_weaknesses(attempts, questions)
    assert len(attempts) == 1
    assert attempts[0]["accuracy"] == 0.5
    assert questions[0]["topic"].startswith("Mixed-topic assignment:")
    assert "correct" not in attempts[0]


@pytest.mark.parametrize("score", [None, "bad", float("nan"), float("inf"), -1, True])
def test_invalid_scores_are_not_performance_evidence(score):
    assert build_attempts_and_questions_from_completions(
        [{"assignment_id": "a1", "score": score}],
        {"a1": {"problems": ["Truth tables"]}},
    ) == ([], [])


def test_unknown_point_scale_is_not_guessed():
    assert build_attempts_and_questions_from_completions(
        [{"assignment_id": "a1", "score": 85}], {"a1": {"title": "Logic"}},
    ) == ([], [])


def test_assignment_without_problems_preserves_fractional_credit():
    attempts, questions = build_attempts_and_questions_from_completions(
        [{"assignment_id": "a1", "score": 75}],
        {"a1": {"title": "Logic", "total_points": 100}},
    )
    assert analyze_student_weaknesses(attempts, questions)[0]["accuracy"] == 0.75
