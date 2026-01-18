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
