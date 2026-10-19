import json
from typing import List, Dict, Any

STUDENT_RECOMMENDATION_SYSTEM_PROMPT = """You are Rocky, an expert educational AI assistant for discrete mathematics and philosophical logic.
Your job is to provide grounded, constructive study recommendations based strictly on deterministic student performance analytics.

Guidelines:
1. Do NOT invent scores or assume topics outside of the provided performance data.
2. For each identified weak topic, explain WHY it deserves attention, assign an appropriate priority ("high", "medium", or "low"), and list 2-4 specific mathematical/logical concepts the student should review.
3. Keep reasons concise, pedagogical, and actionable.
4. Output MUST be valid JSON only. Do not include markdown formatting or commentary outside the JSON block.

Expected JSON schema:
{
  "recommendations": [
    {
      "topic": "<string>",
      "priority": "high" | "medium" | "low",
      "reason": "<concise explanation grounded in the student's performance>",
      "concepts_to_review": [
        "<specific concept 1>",
        "<specific concept 2>"
      ]
    }
  ]
}
"""

PROFESSOR_RECOMMENDATION_SYSTEM_PROMPT = """You are Rocky, an instructional assistant for professors teaching discrete mathematics and philosophical logic.
Your job is to provide actionable lecture review guidance based on class-wide performance metrics.

Guidelines:
1. Do NOT invent grades or topic statistics; rely strictly on the provided aggregate class performance.
2. For each struggling topic, identify key stumbling blocks to clarify during lecture, assign a priority ("high", "medium", or "low"), and suggest specific concepts or examples to review with the class.
3. Keep suggestions concise, pedagogical, and instructional.
4. Output MUST be valid JSON only. Do not include markdown formatting or commentary outside the JSON block.

Expected JSON schema:
{
  "recommendations": [
    {
      "topic": "<string>",
      "priority": "high" | "medium" | "low",
      "reason": "<instructional guidance based on class accuracy and attempt volume>",
      "concepts_to_review": [
        "<stumbling block or concept to re-explain in lecture>",
        "<recommended practice problem type>"
      ]
    }
  ]
}
"""


def build_student_recommendation_prompt(weak_topics: List[Dict[str, Any]]) -> str:
    """
    constructs a grounded prompt for Rocky to generate student study recommendations

    args:
        weak_topics: List of weak topic dictionaries with keys:
                     'topic', 'accuracy', 'questions_attempted'
    """
    if not weak_topics:
        return (
            f"{STUDENT_RECOMMENDATION_SYSTEM_PROMPT}\n\n"
            "Context: The student has mastered all attempted topics with high accuracy.\n"
            "Task: Recommend 1-2 advanced enrichment concepts in discrete mathematics and logic "
            "for continuous learning.\n"
            "Output JSON now:"
        )

    lines = [STUDENT_RECOMMENDATION_SYSTEM_PROMPT, "\nStudent Performance Summary (Deterministic Analytics):"]
    for idx, t in enumerate(weak_topics, 1):
        accuracy_pct = int(round(t.get('accuracy', 0.0) * 100))
        attempts = t.get('questions_attempted', 0)
        topic_name = t.get('topic', 'Unknown')
        lines.append(f"{idx}. Topic: {topic_name} | Accuracy: {accuracy_pct}% | Questions Attempted: {attempts}")

    lines.append(
        "\nDeterministic Recommendation Logic:\n"
        f"'{weak_topics[0].get('topic')}' is currently the student's highest-priority weak area.\n\n"
        "Task: Generate structured recommendations with specific concepts to review for each weak topic.\n"
        "Return ONLY the raw JSON object adhering to the specified schema."
    )

    return "\n".join(lines)


def build_professor_recommendation_prompt(class_weak_topics: List[Dict[str, Any]]) -> str:
    """
    constructs a grounded prompt for Rocky to generate lecture review guidance for professors

    args:
        class_weak_topics: List of class-wide weak topics with keys:
                           'topic', 'accuracy', 'questions_attempted', 'students_attempted'
    """
    if not class_weak_topics:
        return (
            f"{PROFESSOR_RECOMMENDATION_SYSTEM_PROMPT}\n\n"
            "Context: The class is performing strongly across all attempted topics.\n"
            "Task: Suggest 1-2 optional extension/enrichment topics or real-world applications to explore.\n"
            "Output JSON now:"
        )

    lines = [PROFESSOR_RECOMMENDATION_SYSTEM_PROMPT, "\nClass-Wide Performance Summary (Deterministic Analytics):"]
    for idx, t in enumerate(class_weak_topics, 1):
        accuracy_pct = int(round(t.get('accuracy', 0.0) * 100))
        attempts = t.get('questions_attempted', 0)
        students = t.get('students_attempted', 0)
        topic_name = t.get('topic', 'Unknown')
        lines.append(
            f"{idx}. Topic: {topic_name} | Class Accuracy: {accuracy_pct}% "
            f"| Total Attempts: {attempts} | Students Attempted: {students}"
        )

    lines.append(
        "\nDeterministic Recommendation Logic:\n"
        f"Class struggled most with '{class_weak_topics[0].get('topic')}'.\n\n"
        "Task: Recommend targeted topics, stumbling blocks, and concepts for the professor to address in upcoming lectures.\n"
        "Return ONLY the raw JSON object adhering to the specified schema."
    )

    return "\n".join(lines)

