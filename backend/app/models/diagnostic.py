from sqlalchemy import (
    Column,
    Integer,
    Enum,
    ForeignKey,
    DateTime,
    Float,
    func,
    JSON,
)
from sqlalchemy.orm import relationship
from ..database import Base
import enum


class DimensionName(str, enum.Enum):
    ABSTRACTION = "abstraction"
    DECOMPOSITION = "decomposition"
    PATTERNS = "patterns"
    ALGORITHMS = "algorithms"


class QuestionType(str, enum.Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    ORDERING = "ordering"


class Dimension(Base):
    __tablename__ = "dimensions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Enum(DimensionName), unique=True, nullable=False)

    # Relaciones
    questions = relationship("DiagnosticQuestion", back_populates="dimension")


class DiagnosticQuestion(Base):
    __tablename__ = "diagnostic_questions"

    id = Column(Integer, primary_key=True, index=True)
    dimension_id = Column(Integer, ForeignKey("dimensions.id"), nullable=False)
    question_type = Column(Enum(QuestionType), nullable=False)
    content = Column(JSON, nullable=False)  # Guarda el texto y las opciones
    correct_answer = Column(JSON, nullable=False)  # Guarda la respuesta correcta
    points = Column(Integer, default=1)  # Puntaje por pregunta

    # Relaciones
    dimension = relationship("Dimension", back_populates="questions")


class DiagnosticAttempt(Base):
    __tablename__ = "diagnostic_attempts"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    total_score = Column(Float, nullable=True)
    max_score = Column(Integer, default=28)  # Asumiendo 28 preguntas de 1 punto

    # Relaciones
    student = relationship("User")
    answers = relationship("DiagnosticAnswer", back_populates="attempt")


class DiagnosticAnswer(Base):
    __tablename__ = "diagnostic_answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("diagnostic_attempts.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("diagnostic_questions.id"), nullable=False)
    student_answer = Column(JSON, nullable=False)  # La respuesta que dio el estudiante
    is_correct = Column(Integer, nullable=True)  # 1 si es correcta, 0 si no
    time_spent = Column(Integer, nullable=True)  # Segundos tardados (opcional)

    # Relaciones
    attempt = relationship("DiagnosticAttempt", back_populates="answers")
    question = relationship("DiagnosticQuestion")
