from pydantic import BaseModel
from typing import List
from datetime import datetime
from ..models.diagnostic import DimensionName, QuestionType


class QuestionResponse(BaseModel):
    id: int
    dimension: DimensionName
    question_type: QuestionType
    content: dict  # JSON con el texto y opciones
    # No enviamos correct_answer al frontend por seguridad

    class Config:
        from_attributes = True


class AnswerSubmit(BaseModel):
    question_id: int
    student_answer: (
        dict  # La respuesta del estudiante (ej: {"option": "A"} o {"order": [1, 3, 2]})
    )


class AttemptSubmit(BaseModel):
    answers: List[AnswerSubmit]


class DimensionScore(BaseModel):
    dimension: DimensionName
    score: float
    max_score: int


class AttemptResponse(BaseModel):
    id: int
    student_id: int
    total_score: float
    max_score: int
    completed_at: datetime
    scores_by_dimension: List[DimensionScore]

    class Config:
        from_attributes = True
