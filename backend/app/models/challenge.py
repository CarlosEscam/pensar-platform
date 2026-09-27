from sqlalchemy import (
    Column,
    Integer,
    String,
    Enum,
    ForeignKey,
    DateTime,
    Float,
    func,
    JSON,
    Boolean,
)
from sqlalchemy.orm import relationship
from ..database import Base
import enum


class DifficultyLevel(str, enum.Enum):
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ChallengeType(str, enum.Enum):
    CLOSED = "closed"  # Selección múltiple / ordenar pasos
    SEMI_STRUCTURED = "semi_structured"  # Agrupar/dividir
    BLOCKS = "blocks"  # Programación visual (futuro)


class Challenge(Base):
    __tablename__ = "challenges"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(String(500), nullable=False)
    dimension_id = Column(Integer, ForeignKey("dimensions.id"), nullable=False)
    difficulty = Column(Enum(DifficultyLevel), nullable=False)
    challenge_type = Column(
        Enum(ChallengeType), nullable=False, default=ChallengeType.CLOSED
    )

    # Para retos cerrados: content tiene las opciones, correct_answer tiene la respuesta exacta
    content = Column(JSON, nullable=False)
    correct_answer = Column(JSON, nullable=False)
    points_reward = Column(Integer, default=10)  # Puntos que gana al resolverlo

    # Relaciones
    dimension = relationship("Dimension")
    attempts = relationship("ChallengeAttempt", back_populates="challenge")


class ChallengeAttempt(Base):
    __tablename__ = "challenge_attempts"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    submitted_answer = Column(JSON, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    points_earned = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relaciones
    student = relationship("User")
    challenge = relationship("Challenge", back_populates="attempts")


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    total_points = Column(Integer, default=0)
    current_level = Column(Integer, default=1)
    current_streak = Column(Integer, default=0)  # Días consecutivos resolviendo retos

    # Relación
    user = relationship("User")
