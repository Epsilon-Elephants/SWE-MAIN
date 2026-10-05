from dataclasses import dataclass, field, asdict
from typing import List, Optional, Literal, Dict, Any

PriorityLevel = Literal["high", "medium", "low"]

@dataclass
class TopicWeakness:
    """
    deterministic topic metrics calculated by the analyzer
    """
    topic: str
    accuracy: float
    questions_attempted: int

@dataclass
class TopicRecommendation:
    """
    structured recommendation generated for a specific topic
    """
    topic: str
    priority: PriorityLevel
    reason: str
    concepts_to_review: List[str] = field(default_factory=list)

@dataclass
class RecommendationReport:
    """
    complete structured output consumed by the dashboard / UI
    """
    target_type: Literal["student", "class"]
    ranked_weaknesses: List[Dict[str, Any]]
    recommendations: List[TopicRecommendation]
    raw_response: Optional[str] = None
    target_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """convert report to dictionary format for Streamlit or JSON serialization"""
        return {
            "target_type": self.target_type,
            "target_id": self.target_id,
            "ranked_weaknesses": self.ranked_weaknesses,
            "recommendations": [asdict(rec) for rec in self.recommendations],
            "raw_response": self.raw_response,
        }

def validate_recommendation_item(item: Dict[str, Any]) -> TopicRecommendation:
    """
    validates and normalizes a single recommendation item dictionary
    """
    topic = item.get("topic")
    reason = item.get("reason")
    if not isinstance(topic, str) or not topic.strip():
        raise ValueError("Recommendation topic must be nonblank text.")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Recommendation reason must be nonblank text.")
    topic = topic.strip()
    reason = reason.strip()
    priority_raw = str(item.get("priority", "medium")).lower()
    priority: PriorityLevel = priority_raw if priority_raw in ("high", "medium", "low") else "medium"
    
    concepts_raw = item.get("concepts_to_review", [])
    if isinstance(concepts_raw, list):
        concepts = [str(c).strip() for c in concepts_raw if str(c).strip()]
    elif isinstance(concepts_raw, str):
        concepts = [c.strip() for c in concepts_raw.split(",") if c.strip()]
    else:
        concepts = []

    return TopicRecommendation(
        topic=topic,
        priority=priority,
        reason=reason,
        concepts_to_review=concepts
    )

