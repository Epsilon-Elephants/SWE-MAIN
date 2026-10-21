from typing import TypedDict, Optional
from datetime import datetime

# these models represent the expected structure of documents in MongoDB
# the reccomendation engine will use these to analyze student performance

class Question(TypedDict):
    """
    Represents a homework or practice question.
    The recommendation engine relies heavily on the 'topic' field to group student performance.
    """
    _id: Optional[str]
    assignment_id: str
    topic: str
    subtopic: Optional[str]
    difficulty: Optional[int]  # 1 to 5

class Attempt(TypedDict):
    """
    Represents a student's attempt at answering a specific question.
    The recommendation engine uses 'correct' to calculate accuracy per topic.
    """
    _id: Optional[str]
    student_id: str
    question_id: str  # References a Question._id
    correct: bool
    timestamp: datetime

