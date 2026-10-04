from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models.user import User, UserRole
from ..models.diagnostic import (
    Dimension,
    DimensionName,
    DiagnosticQuestion,
    DiagnosticAttempt,
    DiagnosticAnswer,
    QuestionType,
)
from ..schemas.diagnostic import (
    QuestionResponse,
    AttemptSubmit,
    AttemptResponse,
    DimensionScore,
)
from ..core.config import TOTAL_DIAGNOSTIC_QUESTIONS
from ..utils.jwt import get_current_user, require_roles
from datetime import datetime, timezone

router = APIRouter(prefix="/diagnostic", tags=["Diagnostic"])


# --- ENDPOINT DE PRUEBA: Llenar base de datos con preguntas de ejemplo ---
@router.post("/seed")
def seed_diagnostic_questions(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Crea dimensiones y preguntas de prueba (solo para desarrollo)"""
    # 1. Crear dimensiones si no existen
    for dim_name in DimensionName:
        if not db.query(Dimension).filter(Dimension.name == dim_name).first():
            db.add(Dimension(name=dim_name))
    db.commit()

    # 2. Crear una pregunta de prueba por dimensión
    dimensions = db.query(Dimension).all()
    for dim in dimensions:
        # Evitar duplicados en pruebas repetidas
        if (
            db.query(DiagnosticQuestion)
            .filter(DiagnosticQuestion.dimension_id == dim.id)
            .first()
        ):
            continue

        question = DiagnosticQuestion(
            dimension_id=dim.id,
            question_type=QuestionType.MULTIPLE_CHOICE,
            content={
                "text": f"Pregunta de prueba para {dim.name.value}",
                "options": ["A", "B", "C"],
            },
            correct_answer={"correct": "A"},
            points=1,
        )
        db.add(question)
    db.commit()
    return {"message": "Base de datos de diagnóstico poblada con preguntas de prueba."}


# --- ENDPOINTS REALES ---


@router.get("/questions", response_model=List[QuestionResponse])
def get_diagnostic_questions(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Obtiene todas las preguntas del diagnóstico (sin las respuestas correctas)."""
    questions = db.query(DiagnosticQuestion).all()

    # Mapeamos manualmente para evitar conflictos de serialización de relaciones de SQLAlchemy
    response_data = [
        {
            "id": q.id,
            "dimension": q.dimension.name.value,  # Extrae el string del enum (ej: "abstraction")
            "question_type": q.question_type.value,  # Extrae el string del enum (ej: "multiple_choice")
            "content": q.content,
        }
        for q in questions
    ]

    return response_data


@router.post("/attempts", response_model=dict)
def start_diagnostic_attempt(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Inicia un nuevo intento de diagnóstico para el estudiante."""
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=403,
            detail="Solo los estudiantes pueden realizar el diagnóstico.",
        )

    # Verificar si ya tiene un intento completado (regla de negocio: 1 intento por periodo)
    existing_completed = (
        db.query(DiagnosticAttempt)
        .filter(
            DiagnosticAttempt.student_id == current_user.id,
            DiagnosticAttempt.completed_at.isnot(None),
        )
        .first()
    )

    if existing_completed:
        raise HTTPException(
            status_code=409, detail="Ya has completado el diagnóstico inicial."
        )

    new_attempt = DiagnosticAttempt(
        student_id=current_user.id, max_score=TOTAL_DIAGNOSTIC_QUESTIONS
    )
    db.add(new_attempt)
    db.commit()
    db.refresh(new_attempt)

    return {"attempt_id": new_attempt.id, "message": "Intento iniciado. ¡Buena suerte!"}


@router.post("/attempts/{attempt_id}/submit", response_model=AttemptResponse)
def submit_diagnostic_attempt(
    attempt_id: int,
    submission: AttemptSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Envía las respuestas, califica automáticamente y guarda el resultado por dimensión."""
    attempt = (
        db.query(DiagnosticAttempt)
        .filter(
            DiagnosticAttempt.id == attempt_id,
            DiagnosticAttempt.student_id == current_user.id,
        )
        .first()
    )

    if not attempt:
        raise HTTPException(status_code=404, detail="Intento no encontrado.")
    if attempt.completed_at:
        raise HTTPException(status_code=400, detail="Este intento ya fue enviado.")

    # Validar el envío ANTES de modificar cualquier estado (BUG-09 y BUG-12)
    ids = [a.question_id for a in submission.answers]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=400, detail="Hay preguntas repetidas en el envío.")
    questions = {
        q.id: q
        for q in db.query(DiagnosticQuestion).filter(DiagnosticQuestion.id.in_(ids)).all()
    }
    unknown = sorted(set(ids) - set(questions))
    if unknown:
        raise HTTPException(status_code=422, detail=f"Preguntas inexistentes: {unknown}")

    total_score = 0.0
    dimension_scores = {}

    for ans_data in submission.answers:
        question = questions[ans_data.question_id]

        # Lógica simple de calificación (compara el JSON de respuesta con el correcto)
        is_correct = 1 if ans_data.student_answer == question.correct_answer else 0
        points_earned = question.points if is_correct else 0
        total_score += points_earned

        # Guardar la respuesta individual
        db_answer = DiagnosticAnswer(
            attempt_id=attempt_id,
            question_id=question.id,
            student_answer=ans_data.student_answer,
            is_correct=is_correct,
        )
        db.add(db_answer)

        # Acumular puntaje por dimensión
        dim_name = question.dimension.name
        if dim_name not in dimension_scores:
            dimension_scores[dim_name] = {"score": 0.0, "max_score": 0}
        dimension_scores[dim_name]["score"] += points_earned
        dimension_scores[dim_name]["max_score"] += question.points

    # Actualizar el intento con la fecha de finalización y puntaje total
    attempt.completed_at = datetime.now(timezone.utc)
    attempt.total_score = total_score
    db.commit()

    # Formatear la respuesta
    scores_list = [
        DimensionScore(dimension=dim, score=data["score"], max_score=data["max_score"])
        for dim, data in dimension_scores.items()
    ]

    return AttemptResponse(
        id=attempt.id,
        student_id=attempt.student_id,
        total_score=attempt.total_score,
        max_score=attempt.max_score,
        completed_at=attempt.completed_at,
        scores_by_dimension=scores_list,
    )
