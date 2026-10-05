import json
import re
import logging
from threading import Lock
from typing import List, Dict, Any, Optional
from bson import ObjectId

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
    Extracts and parses a JSON object from LLM output, handling markdown blocks or extra text.
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
    Hybrid recommendation engine separating deterministic analytics from LLM guidance.
    """

    def __init__(self, rocky_client=None, weakness_threshold: float = 0.70, max_topics: int = 3):
        """
        Args:
            rocky_client: An instance conforming to rocky.py interface (make_payload, send_payload).
                          If None, it can be initialized on demand.
            weakness_threshold: Accuracy cutoff below which a topic is considered a weakness.
            max_topics: Maximum number of weak topics passed to Rocky for guidance.
        """
        self.rocky_client = rocky_client
        self.weakness_threshold = weakness_threshold
        self.max_topics = max_topics
        self._request_lock = Lock()

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

    def _request_recommendations(self, prompt, max_tokens):
        # The client stores a pending payload. Protect initialization and the
        # whole prepare/send transaction when an engine is reused by sessions.
        with self._request_lock:
            client = self._get_rocky_client()
            if client is not None:
                try:
                    client.make_payload(prompt, max_tokens=max_tokens)
                    return client.send_payload()
                except Exception:
                    logger.exception("Error communicating with Rocky")
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
        # Step 1: deterministic analytics
        ranked_weaknesses = analyze_student_weaknesses(attempts, questions)

        # Step 2: deterministic recommendation logic
        priority_weaknesses = filter_weak_topics(
            ranked_weaknesses,
            threshold=self.weakness_threshold,
            max_topics=self.max_topics,
        )

        # Step 3: prompt construction
        prompt = build_student_recommendation_prompt(
            priority_weaknesses, has_performance_data=bool(ranked_weaknesses),
        )

        raw_response = (
            self._request_recommendations(prompt, max_tokens) if ranked_weaknesses else None
        )
        recommendations = self._parse_and_validate(
            raw_response, priority_weaknesses,
            has_performance_data=bool(ranked_weaknesses),
        )

        return RecommendationReport(
            target_type="student",
            target_id=student_id,
            ranked_weaknesses=ranked_weaknesses,
            recommendations=recommendations,
            raw_response=raw_response,
        )

    def get_student_recommendations_from_db(
        self,
        user_id: str | ObjectId,
        db_instance=None,
        max_tokens: int = 400,
    ) -> RecommendationReport:
        """
        Fetches student completion data from MongoDB, converts it via data_adapter,
        and generates recommendations.
        """
        from app.rocky.data_adapter import get_student_performance_from_db
        attempts, questions = get_student_performance_from_db(user_id, db_instance=db_instance)
        return self.get_student_recommendations(
            attempts=attempts,
            questions=questions,
            student_id=str(user_id),
            max_tokens=max_tokens,
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
        prompt = build_professor_recommendation_prompt(
            priority_weaknesses, has_performance_data=bool(ranked_weaknesses),
        )

        raw_response = (
            self._request_recommendations(prompt, max_tokens) if ranked_weaknesses else None
        )
        recommendations = self._parse_and_validate(
            raw_response, priority_weaknesses,
            has_performance_data=bool(ranked_weaknesses),
        )

        return RecommendationReport(
            target_type="class",
            target_id=class_id,
            ranked_weaknesses=ranked_weaknesses,
            recommendations=recommendations,
            raw_response=raw_response,
        )

    def get_class_recommendations_from_db(
        self,
        class_id: str | ObjectId,
        db_instance=None,
        max_tokens: int = 500,
    ) -> RecommendationReport:
        """
        Fetches class completion data from MongoDB, converts it via data_adapter,
        and generates class-wide review recommendations.
        """
        from app.rocky.data_adapter import get_class_performance_from_db
        attempts, questions = get_class_performance_from_db(class_id, db_instance=db_instance)
        return self.get_class_recommendations(
            all_attempts=attempts,
            questions=questions,
            class_id=str(class_id),
            max_tokens=max_tokens,
        )

    def _parse_and_validate(
        self,
        raw_response: Optional[str],
        fallback_topics: List[Dict[str, Any]],
        *,
        has_performance_data: bool = False,
    ) -> List[TopicRecommendation]:
        """
        Parses LLM response JSON into validated TopicRecommendation objects.
        If LLM is unavailable or response is invalid, constructs deterministic fallback recommendations.
        """
        if not has_performance_data:
            return [TopicRecommendation(
                topic="Insufficient data",
                priority="low",
                reason="No scored performance is available. Complete and grade coursework before assessing mastery.",
                concepts_to_review=[],
            )]

        allowed_topics = {item["topic"] for item in fallback_topics}
        if raw_response:
            parsed_json = extract_json_from_llm_output(raw_response)
            if parsed_json and "recommendations" in parsed_json and isinstance(parsed_json["recommendations"], list):
                validated = []
                for item in parsed_json["recommendations"]:
                    if not isinstance(item, dict):
                        continue
                    try:
                        recommendation = validate_recommendation_item(item)
                    except ValueError:
                        continue
                    if allowed_topics and recommendation.topic not in allowed_topics:
                        continue
                    validated.append(recommendation)
                if validated:
                    return validated

        # deterministic fallback if Rocky is unavailable or returns non-JSON
        fallback_recommendations = []
        if not fallback_topics:
            fallback_recommendations.append(
                TopicRecommendation(
                    topic="Overall Mastery",
                    priority="low",
                    reason="Measured performance meets the configured weakness threshold across all attempted topics.",
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


# Convenience calls own their engine and Rocky client for this request.

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
    )

    return engine.get_student_recommendations(attempts, questions, student_id=student_id)


def get_student_recommendations_from_db(
    user_id: str | ObjectId,
    db_instance=None,
    rocky_client=None,
    weakness_threshold: float = 0.70,
    max_topics: int = 3,
) -> RecommendationReport:
    engine = RecommendationEngine(
        rocky_client=rocky_client,
        weakness_threshold=weakness_threshold,
        max_topics=max_topics,
    )

    return engine.get_student_recommendations_from_db(user_id, db_instance=db_instance)


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
    )

    return engine.get_class_recommendations(all_attempts, questions, class_id=class_id)


def get_class_recommendations_from_db(
    class_id: str | ObjectId,
    db_instance=None,
    rocky_client=None,
    weakness_threshold: float = 0.70,
    max_topics: int = 3,
) -> RecommendationReport:
    engine = RecommendationEngine(
        rocky_client=rocky_client,
        weakness_threshold=weakness_threshold,
        max_topics=max_topics,
    )

    return engine.get_class_recommendations_from_db(class_id, db_instance=db_instance)
