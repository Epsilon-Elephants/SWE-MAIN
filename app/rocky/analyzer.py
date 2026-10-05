from collections import defaultdict
from typing import List, Dict

def analyze_student_weaknesses(attempts: list[dict], questions: list[dict]) -> List[Dict]:
    """
    analyzes student performance based on question attempts and correctness
    
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
            
        topic_stats[topic]["total"] += 1
        if attempt.get("correct"):
            topic_stats[topic]["correct"] += 1

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
    for weakness in weaknesses:
        weakness["accuracy"] = round(weakness["accuracy"], 2)

    return weaknesses

