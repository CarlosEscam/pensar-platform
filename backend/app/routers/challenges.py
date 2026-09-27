from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.user import User, UserRole
from ..models.challenge import (
    Challenge,
    ChallengeAttempt,
    StudentProfile,
    ChallengeType,
)
from ..schemas.challenge import (
    ChallengeCreate,
    ChallengeResponse,
    ChallengeSubmit,
    AttemptResult,
)
from ..utils.jwt import get_current_user

router = APIRouter(prefix="/challenges", tags=["Challenges"])


# --- ENDPOINT PARA DOCENTES/ADMIN: Crear un reto ---
@router.post("/", response_model=ChallengeResponse, status_code=status.HTTP_201_CREATED)
def create_challenge(
    challenge_data: ChallengeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [UserRole.TEACHER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=403,
            detail="Solo docentes o administradores pueden crear retos.",
        )

    new_challenge = Challenge(**challenge_data.dict())
    db.add(new_challenge)
    db.commit()
    db.refresh(new_challenge)

    # Formatear respuesta
    return {
        "id": new_challenge.id,
        "title": new_challenge.title,
        "description": new_challenge.description,
        "dimension": new_challenge.dimension.name.value,
        "difficulty": new_challenge.difficulty.value,
        "challenge_type": new_challenge.challenge_type.value,
        "content": new_challenge.content,
        "points_reward": new_challenge.points_reward,
    }


# --- ENDPOINT PARA ESTUDIANTES: Ver retos disponibles ---
@router.get("/", response_model=list[ChallengeResponse])
def get_available_challenges(
    dimension: str = None,
    difficulty: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Challenge).filter(Challenge.challenge_type == ChallengeType.CLOSED)

    if dimension:
        # Nota: En una implementación real, haríamos un join con Dimension, pero por simplicidad:
        pass  # Se puede mejorar con un join, por ahora devuelve todos los cerrados

    challenges = query.all()

    # Mapeo manual para evitar errores de serialización de Enums/Relaciones
    response_data = []
    for c in challenges:
        response_data.append(
            {
                "id": c.id,
                "title": c.title,
                "description": c.description,
                "dimension": c.dimension.name.value,
                "difficulty": c.difficulty.value,
                "challenge_type": c.challenge_type.value,
                "content": c.content,
                "points_reward": c.points_reward,
            }
        )
    return response_data


# --- ENDPOINT PARA ESTUDIANTES: Resolver un reto (Gamificación) ---
@router.post("/{challenge_id}/attempt", response_model=AttemptResult)
def submit_challenge_attempt(
    challenge_id: int,
    submission: ChallengeSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=403, detail="Solo los estudiantes pueden resolver retos."
        )

    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Reto no encontrado.")

    is_correct = False

    # --- LÓGICA DE CALIFICACIÓN SEGÚN EL TIPO DE RETO (Tabla 2 del Anteproyecto) ---
    if challenge.challenge_type == ChallengeType.CLOSED:
        # Calificación por respuesta exacta
        is_correct = submission.submitted_answer == challenge.correct_answer

    elif challenge.challenge_type == ChallengeType.SEMI_STRUCTURED:
        # Calificación por coincidencia con CUALQUIERA de las estructuras válidas predefinidas
        if not challenge.valid_structures:
            raise HTTPException(
                status_code=500,
                detail="El reto semi-estructurado no tiene estructuras válidas definidas.",
            )

        # Comparamos la respuesta del estudiante con la lista de respuestas aceptadas
        is_correct = submission.submitted_answer in challenge.valid_structures

    else:
        raise HTTPException(
            status_code=400,
            detail="Tipo de reto no soportado en este endpoint (ej. bloques).",
        )

    # Calcular puntos
    points_earned = challenge.points_reward if is_correct else 0

    # Registrar el intento
    attempt = ChallengeAttempt(
        student_id=current_user.id,
        challenge_id=challenge_id,
        submitted_answer=submission.submitted_answer,
        is_correct=is_correct,
        points_earned=points_earned,
    )
    db.add(attempt)

    # Actualizar perfil de gamificación
    profile = (
        db.query(StudentProfile)
        .filter(StudentProfile.user_id == current_user.id)
        .first()
    )
    if not profile:
        profile = StudentProfile(
            user_id=current_user.id, total_points=0, current_level=1, current_streak=0
        )
        db.add(profile)

    profile.total_points += points_earned
    new_level = (profile.total_points // 50) + 1
    if new_level > profile.current_level:
        profile.current_level = new_level

    db.commit()

    # Retroalimentación
    feedback = (
        "¡Excelente! Tu estructura es correcta."
        if is_correct
        else "Esa no es una forma válida de dividir/agrupar. ¡Revisa el problema e inténtalo de nuevo!"
    )

    return AttemptResult(
        is_correct=is_correct,
        points_earned=points_earned,
        total_points=profile.total_points,
        current_level=profile.current_level,
        feedback=feedback,
    )
