import unittest
from datetime import datetime

import pytest
from bson import ObjectId

from app.rocky.analyzer import analyze_student_weaknesses

pytestmark = [pytest.mark.unit, pytest.mark.regression]

class TestAnalyzer(unittest.TestCase):
    def setUp(self):
        self.questions = [
            {"_id": "q1", "assignment_id": "a1", "topic": "Predicate Logic", "difficulty": 2},
            {"_id": "q2", "assignment_id": "a1", "topic": "Predicate Logic", "difficulty": 3},
            {"_id": "q3", "assignment_id": "a1", "topic": "Set Theory", "difficulty": 1},
            {"_id": "q4", "assignment_id": "a1", "topic": "Propositional Logic", "difficulty": 1},
        ]
        
    def test_analyze_student_weaknesses_basic(self):
        attempts = [
            # Predicate logic: 1/2 (50%)
            {"_id": "att1", "student_id": "s1", "question_id": "q1", "correct": True, "timestamp": datetime.now()},
            {"_id": "att2", "student_id": "s1", "question_id": "q2", "correct": False, "timestamp": datetime.now()},
            # Set theory: 2/2 (100%) - multiple attempts on same question or different
            {"_id": "att3", "student_id": "s1", "question_id": "q3", "correct": True, "timestamp": datetime.now()},
            {"_id": "att4", "student_id": "s1", "question_id": "q3", "correct": True, "timestamp": datetime.now()},
            # Propositional Logic: 0/1 (0%)
            {"_id": "att5", "student_id": "s1", "question_id": "q4", "correct": False, "timestamp": datetime.now()},
        ]
        
        results = analyze_student_weaknesses(attempts, self.questions)
        
        self.assertEqual(len(results), 3)
        
        # Lowest accuracy first
        self.assertEqual(results[0]["topic"], "Propositional Logic")
        self.assertEqual(results[0]["accuracy"], 0.0)
        self.assertEqual(results[0]["questions_attempted"], 1)
        
        self.assertEqual(results[1]["topic"], "Predicate Logic")
        self.assertEqual(results[1]["accuracy"], 0.50)
        self.assertEqual(results[1]["questions_attempted"], 2)
        
        self.assertEqual(results[2]["topic"], "Set Theory")
        self.assertEqual(results[2]["accuracy"], 1.0)
        self.assertEqual(results[2]["questions_attempted"], 2)

    def test_empty_data(self):
        self.assertEqual(analyze_student_weaknesses([], self.questions), [])
        self.assertEqual(analyze_student_weaknesses([{"question_id": "q1", "correct": True}], []), [])

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


def test_accuracy_is_rounded_after_counting_attempts():
    questions = [{"_id": "a", "topic": "Logic"}]
    attempts = [{"question_id": "a", "correct": value} for value in (True, False, False)]
    assert analyze_student_weaknesses(attempts, questions) == [
        {"topic": "Logic", "accuracy": 0.33, "questions_attempted": 3},
    ]


if __name__ == '__main__':
    unittest.main()

