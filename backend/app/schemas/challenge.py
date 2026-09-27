from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class ChallengeCreate(BaseModel):
    title: str
    description: str
    dimension_id: int
    difficulty: str
    challenge_type: str = "closed"
    content: dict
    correct_answer: Optional[dict] = None  # Ahora es opcional
    valid_structures: Optional[List[dict]] = None  # <-- NUEVO
    points_reward: int = 10


class ChallengeResponse(BaseModel):
    id: int
    title: str
    description: str
    dimension: str
    difficulty: str
    challenge_type: str
    content: dict
    points_reward: int
    valid_structures: Optional[List[dict]] = (
        None  # <-- NUEVO (solo el docente debería ver esto en un panel de edición, pero lo dejamos por simplicidad)
    )

    class Config:
        from_attributes = True


class ChallengeSubmit(BaseModel):
    submitted_answer: dict


class AttemptResult(BaseModel):
    is_correct: bool
    points_earned: int
    total_points: int
    current_level: int
    feedback: str
