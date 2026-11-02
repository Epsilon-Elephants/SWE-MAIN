"""Tests for deterministic weakness analytics and ranking logic.

Run without Python's -O option so assertions execute:
    python tests/test_analyzer.py
"""
from datetime import datetime

import pytest
from bson import ObjectId

pytestmark = [pytest.mark.unit, pytest.mark.regression]

from rocky.analyzer import (
    analyze_student_weaknesses,
    analyze_class_weaknesses,
    filter_weak_topics,
)

SAMPLE_QUESTIONS = [
    {"_id": "q1", "assignment_id": "a1", "topic": "Predicate Logic", "difficulty": 2},
    {"_id": "q2", "assignment_id": "a1", "topic": "Predicate Logic", "difficulty": 3},
    {"_id": "q3", "assignment_id": "a1", "topic": "Set Theory", "difficulty": 1},
    {"_id": "q4", "assignment_id": "a1", "topic": "Propositional Logic", "difficulty": 1},
]


def test_analyze_student_weaknesses_basic():
    attempts = [
        # Predicate logic: 1/2 correct (50%)
        {"_id": "att1", "student_id": "s1", "question_id": "q1", "correct": True, "timestamp": datetime.now()},
        {"_id": "att2", "student_id": "s1", "question_id": "q2", "correct": False, "timestamp": datetime.now()},
        # Set theory: 2/2 correct (100%)
        {"_id": "att3", "student_id": "s1", "question_id": "q3", "correct": True, "timestamp": datetime.now()},
        {"_id": "att4", "student_id": "s1", "question_id": "q3", "correct": True, "timestamp": datetime.now()},
        # Propositional logic: 0/1 correct (0%)
        {"_id": "att5", "student_id": "s1", "question_id": "q4", "correct": False, "timestamp": datetime.now()},
    ]

    results = analyze_student_weaknesses(attempts, SAMPLE_QUESTIONS)

    assert len(results) == 3, f"Expected 3 topics, got {len(results)}"

    # Ranked by lowest accuracy first
    assert results[0]["topic"] == "Propositional Logic"
    assert results[0]["accuracy"] == 0.0, f"Expected 0.0, got {results[0]['accuracy']}"
    assert results[0]["questions_attempted"] == 1

    assert results[1]["topic"] == "Predicate Logic"
    assert results[1]["accuracy"] == 0.50, f"Expected 0.50, got {results[1]['accuracy']}"
    assert results[1]["questions_attempted"] == 2

    assert results[2]["topic"] == "Set Theory"
    assert results[2]["accuracy"] == 1.0, f"Expected 1.0, got {results[2]['accuracy']}"
    assert results[2]["questions_attempted"] == 2


def test_empty_attempts_and_questions():
    assert analyze_student_weaknesses([], SAMPLE_QUESTIONS) == []
    assert analyze_student_weaknesses([{"question_id": "q1", "correct": True}], []) == []
    assert analyze_class_weaknesses([], SAMPLE_QUESTIONS) == []
    assert analyze_class_weaknesses([{"question_id": "q1", "correct": True}], []) == []


def test_filter_weak_topics():
    ranked = [
        {"topic": "Predicate Logic", "accuracy": 0.40, "questions_attempted": 10},
        {"topic": "Set Theory", "accuracy": 0.65, "questions_attempted": 20},
        {"topic": "Propositional Logic", "accuracy": 0.90, "questions_attempted": 15},
    ]

    # Default threshold 0.70, max_topics 3 -> Predicate Logic and Set Theory
    weak = filter_weak_topics(ranked, threshold=0.70, max_topics=3)
    assert len(weak) == 2, f"Expected 2 weak topics, got {len(weak)}"
    assert weak[0]["topic"] == "Predicate Logic"
    assert weak[1]["topic"] == "Set Theory"

    # Strict threshold 0.50 -> only Predicate Logic
    weak_strict = filter_weak_topics(ranked, threshold=0.50)
    assert len(weak_strict) == 1
    assert weak_strict[0]["topic"] == "Predicate Logic"

    # Max topics limit 1
    weak_top1 = filter_weak_topics(ranked, threshold=0.70, max_topics=1)
    assert len(weak_top1) == 1
    assert weak_top1[0]["topic"] == "Predicate Logic"


def test_analyze_class_weaknesses():
    attempts = [
        # Student 1
        {"_id": "att1", "student_id": "s1", "question_id": "q1", "correct": True, "timestamp": datetime.now()},
        {"_id": "att2", "student_id": "s1", "question_id": "q2", "correct": False, "timestamp": datetime.now()},
        # Student 2
        {"_id": "att3", "student_id": "s2", "question_id": "q1", "correct": False, "timestamp": datetime.now()},
        {"_id": "att4", "student_id": "s2", "question_id": "q3", "correct": True, "timestamp": datetime.now()},
    ]

    class_results = analyze_class_weaknesses(attempts, SAMPLE_QUESTIONS)
    assert len(class_results) == 2, f"Expected 2 topics, got {len(class_results)}"

    # Predicate Logic: 1 correct out of 3 attempts across 2 students.
    assert class_results[0]["topic"] == "Predicate Logic"
    assert class_results[0]["accuracy"] == pytest.approx(1 / 3), f"Expected 1/3, got {class_results[0]['accuracy']}"
    assert class_results[0]["questions_attempted"] == 3
    assert class_results[0]["students_attempted"] == 2

    # Set Theory: 1 correct out of 1 attempt -> 1.0
    assert class_results[1]["topic"] == "Set Theory"
    assert class_results[1]["accuracy"] == 1.0
    assert class_results[1]["questions_attempted"] == 1
    assert class_results[1]["students_attempted"] == 1


def test_unknown_questions_and_questions_without_topics_are_ignored():
    question_id = ObjectId()
    questions = [{"_id": question_id, "topic": "Logic"},
                 {"_id": "empty", "topic": ""}, {"_id": "missing"}, {"topic": "No ID"}]
    attempts = [{"question_id": str(question_id), "correct": True},
                {"question_id": "unknown", "correct": False},
                {"question_id": "empty", "correct": False},
                {"question_id": "missing", "correct": False}]
    assert analyze_student_weaknesses(attempts, questions) == [
        {"topic": "Logic", "accuracy": 1.0, "questions_attempted": 1},
    ]


def test_equal_accuracy_prioritizes_topic_with_more_attempts():
    questions = [{"_id": "a", "topic": "A"}, {"_id": "b", "topic": "B"}]
    attempts = [{"question_id": "a", "correct": True}, {"question_id": "a", "correct": False},
                *[{"question_id": "b", "correct": value} for value in (True, False, True, False)]]
    assert analyze_student_weaknesses(attempts, questions) == [
        {"topic": "B", "accuracy": 0.5, "questions_attempted": 4},
        {"topic": "A", "accuracy": 0.5, "questions_attempted": 2},
    ]


def test_accuracy_preserves_precision_after_counting_attempts():
    questions = [{"_id": "a", "topic": "Logic"}]
    attempts = [{"question_id": "a", "correct": value} for value in (True, False, False)]
    assert analyze_student_weaknesses(attempts, questions) == [
        {"topic": "Logic", "accuracy": 1 / 3, "questions_attempted": 3},
    ]



def main():
    test_analyze_student_weaknesses_basic()
    test_empty_attempts_and_questions()
    test_filter_weak_topics()
    test_analyze_class_weaknesses()
    print("All analyzer tests passed.")


if __name__ == "__main__":
    main()


@pytest.mark.parametrize("analyzer", [analyze_student_weaknesses, analyze_class_weaknesses])
def test_threshold_uses_unrounded_accuracy(analyzer):
    questions = [{"_id": "q", "topic": "Logic"}]
    attempts = [{"question_id": "q", "correct": index < 16} for index in range(23)]
    ranked = analyzer(attempts, questions)
    assert ranked[0]["accuracy"] == 16 / 23
    assert filter_weak_topics(ranked, threshold=0.7) == ranked


@pytest.mark.parametrize("analyzer", [analyze_student_weaknesses, analyze_class_weaknesses])
def test_numeric_partial_credit_controls_configured_threshold(analyzer):
    ranked = analyzer(
        [{"question_id": "q", "accuracy": 0.75}], [{"_id": "q", "topic": "Logic"}],
    )
    assert ranked[0]["accuracy"] == 0.75
    assert filter_weak_topics(ranked, threshold=0.8) == ranked
    assert filter_weak_topics(ranked, threshold=0.7) == []


@pytest.mark.parametrize("analyzer", [analyze_student_weaknesses, analyze_class_weaknesses])
def test_invalid_attempts_are_not_evidence(analyzer):
    assert analyzer([
        {"question_id": "q"}, {"question_id": "q", "accuracy": float("nan")},
        {"question_id": "q", "accuracy": 5}, {"question_id": "q", "correct": "true"},
    ], [{"_id": "q", "topic": "Logic"}]) == []
