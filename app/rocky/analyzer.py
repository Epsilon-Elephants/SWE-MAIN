import math
from collections import defaultdict
from typing import List, Dict

def _attempt_accuracy(attempt):
    """Accept numeric partial credit or actual boolean per-question grades."""
    if "accuracy" in attempt:
        accuracy = attempt["accuracy"]
        if (isinstance(accuracy, (int, float)) and not isinstance(accuracy, bool)
                and math.isfinite(accuracy) and 0 <= accuracy <= 1):
            return accuracy
        return None
    correct = attempt.get("correct")
    return float(correct) if isinstance(correct, bool) else None


def analyze_student_weaknesses(attempts: list[dict], questions: list[dict]) -> List[Dict]:
    """
    Analyzes boolean question grades or numeric assignment performance.
    Each scored observation counts once; rounding belongs in display formatting.
    
    Args:
        attempts: List of Attempt dictionaries for a specific student.
        questions: List of Question dictionaries corresponding to the attempts.
        
    Returns:
        A list of dictionaries representing topic performance, sorted from lowest accuracy to highest.
        Example: [{"topic": "Predicate Logic", "accuracy": 0.40, "questions_attempted": 10}]
    """
    if not attempts or not questions:
        return []

    # map question_id to topic for O(1) lookup
    question_topics = {str(q.get('_id')): q.get('topic') for q in questions if '_id' in q and 'topic' in q}

    # group performance by topic
    topic_stats = defaultdict(lambda: {"correct": 0, "total": 0})

    for attempt in attempts:
        q_id = str(attempt.get('question_id'))
        topic = question_topics.get(q_id)
        
        if not topic:
            continue
            
        accuracy = _attempt_accuracy(attempt)
        if accuracy is None:
            continue
        topic_stats[topic]["total"] += 1
        topic_stats[topic]["correct"] += accuracy

    # calculate accuracy and format output
    weaknesses = []
    for topic, stats in topic_stats.items():
        accuracy = stats["correct"] / stats["total"] if stats["total"] > 0 else 0.0
        weaknesses.append({
            "topic": topic,
            "accuracy": accuracy,
            "questions_attempted": stats["total"]
        })

    # sort lowest accuracy, then descending by attempts (more attempts = higher confidence in weakness)
    weaknesses.sort(key=lambda x: (x["accuracy"], -x["questions_attempted"]))

    return weaknesses


def analyze_class_weaknesses(attempts: list[dict], questions: list[dict]) -> List[Dict]:
    """
    aggregates performance across all students in a class or course to find class-wide topic weaknesses

    args:
        attempts: List of attempt dictionaries across all students
        questions: List of question dictionaries

    returns:
        a list of dictionaries representing class topic performance, sorted from lowest accuracy to highest
        e.g., [{"topic": "Predicate Logic", "accuracy": 0.51, "questions_attempted": 85, "students_attempted": 22}]
    """
    if not attempts or not questions:
        return []

    question_topics = {str(q.get('_id')): q.get('topic') for q in questions if '_id' in q and 'topic' in q}

    topic_stats = defaultdict(lambda: {"correct": 0, "total": 0, "students": set()})

    for attempt in attempts:
        q_id = str(attempt.get('question_id'))
        topic = question_topics.get(q_id)

        if not topic:
            continue

        accuracy = _attempt_accuracy(attempt)
        if accuracy is None:
            continue
        topic_stats[topic]["total"] += 1
        topic_stats[topic]["correct"] += accuracy

        student_id = attempt.get("student_id")
        if student_id:
            topic_stats[topic]["students"].add(str(student_id))

    class_weaknesses = []
    for topic, stats in topic_stats.items():
        accuracy = stats["correct"] / stats["total"] if stats["total"] > 0 else 0.0
        class_weaknesses.append({
            "topic": topic,
            "accuracy": accuracy,
            "questions_attempted": stats["total"],
            "students_attempted": len(stats["students"])
        })

    class_weaknesses.sort(key=lambda x: (x["accuracy"], -x["questions_attempted"]))
    return class_weaknesses


def filter_weak_topics(
    ranked_topics: List[Dict],
    threshold: float = 0.70,
    max_topics: int = 3
) -> List[Dict]:
    """
    filters and limits ranked topics to identify weaknesses below a given accuracy threshold

    args:
        ranked_topics: List of topic stats sorted by accuracy ascending
        threshold: Accuracy threshold below which a topic is flagged as weak (default is 0.70)
        max_topics: Maximum number of weak topics to return (default is 3)

    returns:
        filtered list of weak topics
    """
    weak = [t for t in ranked_topics if t.get("accuracy", 1.0) < threshold]
    return weak[:max_topics]


