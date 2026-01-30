"""Pydantic models for Neo4j graph entities."""
from pydantic import BaseModel
from typing import Optional


class ConceptNode(BaseModel):
    """Concept node from Neo4j."""
    id: str
    title: str
    description: Optional[str] = None
    section_id: Optional[str] = None
    chapter: Optional[str] = None
    difficulty: Optional[int] = None
    estimated_minutes: Optional[int] = None
    is_prerequisite: Optional[bool] = False
    
    class Config:
        populate_by_name = True
        # Handle Neo4j camelCase to snake_case
        alias_generator = lambda s: ''.join(
            ['_' + c.lower() if c.isupper() else c for c in s]
        ).lstrip('_')


class ExerciseNode(BaseModel):
    """Exercise node from Neo4j."""
    id: str
    question: str


class InsightNode(BaseModel):
    """Insight node representing a specific understanding or misconception about a concept.
    
    Types:
    - COMPETENCY: Student understands this concept/relationship
    - MISCONCEPTION: Student struggles with this concept/relationship
    - PREFERENCE: Student learning preference (e.g., "prefers examples")
    """
    id: str
    type: str  # COMPETENCY, MISCONCEPTION, PREFERENCE
    content: str  # Description of the insight
    confidence: float = 1.0  # 0.0-1.0, how certain the agent is
    created_at: Optional[str] = None  # ISO datetime string
    superseded_by: Optional[str] = None  # ID of newer insight that replaces this one
