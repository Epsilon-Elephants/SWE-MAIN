"""Tests for recommendation engine orchestration, JSON parsing, and fallbacks.

Run without Python's -O option so assertions execute:
    python tests/test_recommendation.py
"""
import json
from datetime import datetime

from app.rocky.recommendation import (
    RecommendationEngine,
    extract_json_from_llm_output,
    get_student_recommendations,
    get_class_recommendations,
)

SAMPLE_QUESTIONS = [
    {"_id": "q1", "assignment_id": "a1", "topic": "Predicate Logic", "difficulty": 2},
    {"_id": "q2", "assignment_id": "a1", "topic": "Predicate Logic", "difficulty": 3},
    {"_id": "q3", "assignment_id": "a1", "topic": "Set Theory", "difficulty": 1},
]

SAMPLE_ATTEMPTS = [
    {"_id": "att1", "student_id": "s1", "question_id": "q1", "correct": False, "timestamp": datetime.now()},
    {"_id": "att2", "student_id": "s1", "question_id": "q2", "correct": False, "timestamp": datetime.now()},
    {"_id": "att3", "student_id": "s1", "question_id": "q3", "correct": True, "timestamp": datetime.now()},
]


class MockRockyClient:
    """Mock for rocky.py to test recommendation flow without API calls."""

    def __init__(self, response_text: str):
        self.response_text = response_text
        self.last_payload = None

    def make_payload(self, inpt: str, max_tokens: int = 300, store: bool = False):
        self.last_payload = {
            "model": "mock-gemma",
            "input": inpt,
            "max_output_tokens": max_tokens,
            "store": store,
        }

    def send_payload(self) -> str:
        return self.response_text


def test_extract_json_from_llm_output_clean():
    raw = '{"recommendations": [{"topic": "Predicate Logic", "priority": "high", "reason": "Low accuracy", "concepts_to_review": ["Quantifiers"]}]}'
    result = extract_json_from_llm_output(raw)
    assert result is not None, "Failed to parse clean JSON"
    assert len(result["recommendations"]) == 1
    assert result["recommendations"][0]["topic"] == "Predicate Logic"


def test_extract_json_from_llm_output_markdown():
    raw = """Here is your study recommendation:
```json
{
  "recommendations": [
    {
      "topic": "Predicate Logic",
      "priority": "high",
      "reason": "Accuracy is 0%",
      "concepts_to_review": ["Quantifiers", "Free vs Bound Variables"]
    }
  ]
}
```
Hope this helps!"""
    result = extract_json_from_llm_output(raw)
    assert result is not None, "Failed to extract JSON from markdown block"
    assert result["recommendations"][0]["topic"] == "Predicate Logic"
    assert len(result["recommendations"][0]["concepts_to_review"]) == 2


def test_extract_json_from_llm_output_invalid():
    raw = "I am an AI and I suggest reviewing predicate logic."
    result = extract_json_from_llm_output(raw)
    assert result is None, "Expected None for non-JSON text"


def test_student_recommendations_with_mock_rocky():
    mock_response = json.dumps({
        "recommendations": [
            {
                "topic": "Predicate Logic",
                "priority": "high",
                "reason": "Student got 0% accuracy across 2 questions.",
                "concepts_to_review": ["Quantifiers", "Variable Binding", "Translation"]
            }
        ]
    })
    client = MockRockyClient(mock_response)
    engine = RecommendationEngine(rocky_client=client)

    report = engine.get_student_recommendations(SAMPLE_ATTEMPTS, SAMPLE_QUESTIONS, student_id="s1")

    assert report.target_type == "student"
    assert report.target_id == "s1"
    assert len(report.recommendations) == 1

    rec = report.recommendations[0]
    assert rec.topic == "Predicate Logic"
    assert rec.priority == "high"
    assert "Quantifiers" in rec.concepts_to_review

    # Verify Rocky was passed grounded deterministic facts
    assert "Predicate Logic" in client.last_payload["input"]
    assert "Accuracy: 0%" in client.last_payload["input"]


def test_fallback_on_invalid_llm_response():
    # LLM returns text that is not valid JSON
    client = MockRockyClient("I think the student should practice more logic questions.")
    engine = RecommendationEngine(rocky_client=client)

    report = engine.get_student_recommendations(SAMPLE_ATTEMPTS, SAMPLE_QUESTIONS, student_id="s1")

    # Fallback recommendations should still be created deterministically without crashing
    assert len(report.recommendations) == 1
    assert report.recommendations[0].topic == "Predicate Logic"
    assert report.recommendations[0].priority == "high"
    assert "0% accuracy" in report.recommendations[0].reason


def test_student_mastery_handling():
    # 100% on everything -> no weak topics below 0.70 threshold
    perfect_attempts = [
        {"_id": "att1", "student_id": "s1", "question_id": "q1", "correct": True, "timestamp": datetime.now()},
        {"_id": "att2", "student_id": "s1", "question_id": "q3", "correct": True, "timestamp": datetime.now()},
    ]
    report = get_student_recommendations(
        perfect_attempts,
        SAMPLE_QUESTIONS,
        student_id="s1",
        rocky_client=None,
    )

    assert report.target_type == "student"
    assert len(report.recommendations) == 1
    assert report.recommendations[0].topic == "Overall Mastery"


def test_class_recommendations():
    mock_response = json.dumps({
        "recommendations": [
            {
                "topic": "Predicate Logic",
                "priority": "high",
                "reason": "Class struggle with predicate logic translations.",
                "concepts_to_review": ["Universal vs existential quantifiers in lecture"]
            }
        ]
    })
    client = MockRockyClient(mock_response)
    report = get_class_recommendations(
        SAMPLE_ATTEMPTS,
        SAMPLE_QUESTIONS,
        class_id="class_101",
        rocky_client=client,
    )

    assert report.target_type == "class"
    assert report.target_id == "class_101"
    assert len(report.recommendations) == 1
    assert report.recommendations[0].topic == "Predicate Logic"


def main():
    test_extract_json_from_llm_output_clean()
    test_extract_json_from_llm_output_markdown()
    test_extract_json_from_llm_output_invalid()
    test_student_recommendations_with_mock_rocky()
    test_fallback_on_invalid_llm_response()
    test_student_mastery_handling()
    test_class_recommendations()
    print("All recommendation tests passed.")


if __name__ == "__main__":
    main()
