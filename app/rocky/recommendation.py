import json
import re
import logging
from typing import List, Dict, Any, Optional

from app.rocky.analyzer import (
    analyze_student_weaknesses,
    analyze_class_weaknesses,
    filter_weak_topics,
)
from app.rocky.prompts import (
    build_student_recommendation_prompt,
    build_professor_recommendation_prompt,
)
from app.rocky.schemas import (
    TopicRecommendation,
    RecommendationReport,
    validate_recommendation_item,
)

logger = logging.getLogger(__name__)


def extract_json_from_llm_output(output_text: str) -> Optional[Dict[str, Any]]:
    """
    extracts and parses a JSON object from LLM output, handling markdown blocks or extra text
    """
    if not output_text or not output_text.strip():
        return None

    cleaned = output_text.strip()

    # remove markdown code blocks if present (```json ... ``` or ``` ... ```)
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()

    # try direct parse
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # fallback: find first '{' and last '}'
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            data = json.loads(cleaned[start : end + 1])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    return None


class RecommendationEngine:
    """
    hybrid recommendation engine separating deterministic analytics from LLM guidance
    """

    def __init__(self, rocky_client=None, weakness_threshold: float = 0.70, max_topics: int = 3):
        """
        args:
            rocky_client: An instance conforming to rocky.py interface (make_payload, send_payload)
            If None, it can be initialized on demand.
            weakness_threshold: Accuracy cutoff below which a topic is considered a weakness.
            max_topics: Maximum number of weak topics passed to Rocky for guidance.
        """
        self.rocky_client = rocky_client
        self.weakness_threshold = weakness_threshold
        self.max_topics = max_topics

    def _get_rocky_client(self):
        if self.rocky_client is not None:
            return self.rocky_client
        try:
            from app.rocky.rocky import rocky
            self.rocky_client = rocky()
            return self.rocky_client
        except Exception as e:
            logger.warning(f"Could not initialize Rocky client: {e}")
            return None

    def get_student_recommendations(
        self,
        attempts: List[Dict[str, Any]],
        questions: List[Dict[str, Any]],
        student_id: Optional[str] = None,
        max_tokens: int = 400,
    ) -> RecommendationReport:
        """
        1. deterministically calculates topic weaknesses for a student
        2. filters highest-priority weak areas
        3. grounds Rocky with calculated facts
        4. validates and returns structured recommendations
        """
        # step 1: deterministic analytics
        ranked_weaknesses = analyze_student_weaknesses(attempts, questions)

        # step 2: deterministic recommendation logic
        priority_weaknesses = filter_weak_topics(
            ranked_weaknesses,
            threshold=self.weakness_threshold,
            max_topics=self.max_topics,
        )

        # step 3: prompt construction
        prompt = build_student_recommendation_prompt(priority_weaknesses)

        # step 4: rocky / gemma Inference
        client = self._get_rocky_client()
        raw_response = None
        recommendations: List[TopicRecommendation] = []

        if client is not None:
            try:
                client.make_payload(prompt, max_tokens=max_tokens)
                raw_response = client.send_payload()
            except Exception as e:
                logger.error(f"Error communicating with Rocky: {e}")

        # step 5: parsing & validation
        recommendations = self._parse_and_validate(raw_response, priority_weaknesses)

        return RecommendationReport(
            target_type="student",
            target_id=student_id,
            ranked_weaknesses=ranked_weaknesses,
            recommendations=recommendations,
            raw_response=raw_response,
        )

    def get_class_recommendations(
        self,
        all_attempts: List[Dict[str, Any]],
        questions: List[Dict[str, Any]],
        class_id: Optional[str] = None,
        max_tokens: int = 500,
    ) -> RecommendationReport:
        """
        1. aggregates performance across all students in a class
        2. filters class-wide weak areas
        3. grounds Rocky with aggregate facts
        4. returns structured instructional review recommendations for the professor
        """
        # Step 1: class-wide deterministic analytics
        ranked_weaknesses = analyze_class_weaknesses(all_attempts, questions)

        # Step 2: deterministic recommendation logic
        priority_weaknesses = filter_weak_topics(
            ranked_weaknesses,
            threshold=self.weakness_threshold,
            max_topics=self.max_topics,
        )

        # Step 3: prompt construction
        prompt = build_professor_recommendation_prompt(priority_weaknesses)

        # Step 4: rocky inference
        client = self._get_rocky_client()
        raw_response = None

        if client is not None:
            try:
                client.make_payload(prompt, max_tokens=max_tokens)
                raw_response = client.send_payload()
            except Exception as e:
                logger.error(f"Error communicating with Rocky for class recommendations: {e}")

        # Step 5: parsing & validation
        recommendations = self._parse_and_validate(raw_response, priority_weaknesses)

        return RecommendationReport(
            target_type="class",
            target_id=class_id,
            ranked_weaknesses=ranked_weaknesses,
            recommendations=recommendations,
            raw_response=raw_response,
        )

    def _parse_and_validate(
        self,
        raw_response: Optional[str],
        fallback_topics: List[Dict[str, Any]],
    ) -> List[TopicRecommendation]:
        """
        Parses LLM response JSON into validated TopicRecommendation objects.
        If LLM is unavailable or response is invalid, constructs deterministic fallback recommendations.
        """
        if raw_response:
            parsed_json = extract_json_from_llm_output(raw_response)
            if parsed_json and "recommendations" in parsed_json and isinstance(parsed_json["recommendations"], list):
                validated = []
                for item in parsed_json["recommendations"]:
                    if isinstance(item, dict):
                        validated.append(validate_recommendation_item(item))
                if validated:
                    return validated

        # deterministic fallback if Rocky is unavailable or returns non-JSON
        fallback_recommendations = []
        if not fallback_topics:
            fallback_recommendations.append(
                TopicRecommendation(
                    topic="Overall Mastery",
                    priority="low",
                    reason="Student has scored above the weakness threshold across all attempted topics.",
                    concepts_to_review=["Advanced logic practice", "Independent study"],
                )
            )
        else:
            for idx, item in enumerate(fallback_topics):
                topic = item.get("topic", "Logic Topic")
                accuracy_pct = int(round(item.get("accuracy", 0.0) * 100))
                priority = "high" if idx == 0 else "medium"
                fallback_recommendations.append(
                    TopicRecommendation(
                        topic=topic,
                        priority=priority,
                        reason=f"Identified as priority review area with {accuracy_pct}% accuracy over {item.get('questions_attempted', 0)} attempts.",
                        concepts_to_review=[f"Core {topic} definitions", f"{topic} problem practice"],
                    )
                )

        return fallback_recommendations


# convenience functions for direct use by Streamlit dashboards
_default_engine = RecommendationEngine()

def get_student_recommendations(
    attempts: List[Dict[str, Any]],
    questions: List[Dict[str, Any]],
    student_id: Optional[str] = None,
    rocky_client=None,
    weakness_threshold: float = 0.70,
    max_topics: int = 3,
) -> RecommendationReport:
    engine = RecommendationEngine(
        rocky_client=rocky_client,
        weakness_threshold=weakness_threshold,
        max_topics=max_topics,
    ) if (rocky_client or weakness_threshold != 0.70 or max_topics != 3) else _default_engine

    return engine.get_student_recommendations(attempts, questions, student_id=student_id)


def get_class_recommendations(
    all_attempts: List[Dict[str, Any]],
    questions: List[Dict[str, Any]],
    class_id: Optional[str] = None,
    rocky_client=None,
    weakness_threshold: float = 0.70,
    max_topics: int = 3,
) -> RecommendationReport:
    engine = RecommendationEngine(
        rocky_client=rocky_client,
        weakness_threshold=weakness_threshold,
        max_topics=max_topics,
    ) if (rocky_client or weakness_threshold != 0.70 or max_topics != 3) else _default_engine

    return engine.get_class_recommendations(all_attempts, questions, class_id=class_id)

