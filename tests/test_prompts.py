"""Tests for prompt builder module.

Run without Python's -O option so assertions execute:
    python tests/test_prompts.py
"""
from app.rocky.prompts import (
    build_student_recommendation_prompt,
    build_professor_recommendation_prompt,
)


def test_student_recommendation_prompt_with_weaknesses():
    weak_topics = [
        {"topic": "Predicate Logic", "accuracy": 0.40, "questions_attempted": 10},
        {"topic": "Set Theory", "accuracy": 0.65, "questions_attempted": 20},
    ]
    prompt = build_student_recommendation_prompt(weak_topics)

    assert "Predicate Logic" in prompt, "Missing Predicate Logic in student prompt"
    assert "40%" in prompt, "Missing 40% accuracy in prompt"
    assert "Questions Attempted: 10" in prompt, "Missing questions attempted"
    assert "Set Theory" in prompt, "Missing Set Theory in prompt"
    assert "65%" in prompt, "Missing 65% accuracy in prompt"
    assert "Questions Attempted: 20" in prompt, "Missing questions attempted for Set Theory"
    assert "'Predicate Logic' is currently the student's highest-priority weak area" in prompt
    assert "concepts_to_review" in prompt, "Missing schema guidance for concepts_to_review"


def test_student_recommendation_prompt_empty_mastery():
    prompt = build_student_recommendation_prompt([], has_performance_data=True)
    assert "meets the configured weakness threshold" in prompt, "Expected mastery messaging when weak_topics is empty"
    assert "enrichment" in prompt, "Expected enrichment guidance for mastery"


def test_professor_recommendation_prompt_with_weaknesses():
    class_weak_topics = [
        {
            "topic": "Predicate Logic",
            "accuracy": 0.51,
            "questions_attempted": 85,
            "students_attempted": 22,
        }
    ]
    prompt = build_professor_recommendation_prompt(class_weak_topics)

    assert "Predicate Logic" in prompt, "Missing topic in professor prompt"
    assert "51%" in prompt, "Missing accuracy percentage in professor prompt"
    assert "Total Attempts: 85" in prompt, "Missing total attempt count in professor prompt"
    assert "Students Attempted: 22" in prompt, "Missing distinct student count in professor prompt"
    assert "Class struggled most with 'Predicate Logic'" in prompt


def test_professor_recommendation_prompt_empty_mastery():
    prompt = build_professor_recommendation_prompt([], has_performance_data=True)
    assert "meets the configured weakness threshold" in prompt
    assert "enrichment" in prompt or "extension" in prompt


def main():
    test_student_recommendation_prompt_with_weaknesses()
    test_student_recommendation_prompt_empty_mastery()
    test_professor_recommendation_prompt_with_weaknesses()
    test_professor_recommendation_prompt_empty_mastery()
    print("All prompt tests passed.")


if __name__ == "__main__":
    main()


def test_empty_history_prompts_do_not_assert_mastery():
    for builder in (build_student_recommendation_prompt, build_professor_recommendation_prompt):
        prompt = builder([])
        assert "insufficient data" in prompt
        assert "meets the configured weakness threshold" not in prompt
        assert "mastered" not in prompt
