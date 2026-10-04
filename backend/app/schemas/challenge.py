from pydantic import BaseModel, ConfigDict
from typing import List, Optional

from ..models.challenge import ChallengeType, DifficultyLevel


class ChallengeCreate(BaseModel):
    title: str
    description: str
    dimension_id: int
    difficulty: DifficultyLevel
    challenge_type: ChallengeType = ChallengeType.CLOSED
    content: dict
    correct_answer: Optional[dict] = None
    valid_structures: Optional[List[dict]] = None
    points_reward: int = 10


class ChallengeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    dimension: str
    difficulty: str
    challenge_type: str
    content: dict
    points_reward: int
    # Solo se devuelve al crear el reto (vista del docente); el listado para
    # estudiantes nunca lo incluye.
    valid_structures: Optional[List[dict]] = None


class ChallengeSubmit(BaseModel):
    submitted_answer: dict


class AttemptResult(BaseModel):
    is_correct: bool
    points_earned: int
    total_points: int
    current_level: int
    feedback: str
