from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.user import User, UserRole
from ..models.diagnostic import Dimension, DimensionName
from ..models.challenge import (
    Challenge,
    ChallengeAttempt,
    StudentProfile,
    ChallengeType,
    DifficultyLevel,
)
from ..schemas.challenge import (
    ChallengeCreate,
    ChallengeResponse,
    ChallengeSubmit,
    AttemptResult,
)
from ..services.graders import get_grader
from ..utils.jwt import get_current_user

router = APIRouter(prefix="/challenges", tags=["Challenges"])


def _to_response(c: Challenge, include_structures: bool = False) -> dict:
    data = {
        "id": c.id,
        "title": c.title,
        "description": c.description,
        "dimension": c.dimension.name.value,
        "difficulty": c.difficulty.value,
        "challenge_type": c.challenge_type.value,
        "content": c.content,
        "points_reward": c.points_reward,
    }
    if include_structures:
        data["valid_structures"] = c.valid_structures
    return data


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

    if not db.query(Dimension).filter(Dimension.id == challenge_data.dimension_id).first():
        raise HTTPException(status_code=404, detail="La dimensión indicada no existe.")

    if challenge_data.challenge_type == ChallengeType.SEMI_STRUCTURED:
        # RF-02: un reto semi-estructurado exige al menos dos estructuras válidas
        if not challenge_data.valid_structures or len(challenge_data.valid_structures) < 2:
            raise HTTPException(
                status_code=400,
                detail="Un reto semi-estructurado requiere al menos 2 estructuras válidas.",
            )
    elif challenge_data.challenge_type == ChallengeType.CLOSED:
        if not challenge_data.correct_answer:
            raise HTTPException(
                status_code=400, detail="Un reto cerrado requiere correct_answer."
            )

    new_challenge = Challenge(**challenge_data.model_dump())
    db.add(new_challenge)
    db.commit()
    db.refresh(new_challenge)

    return _to_response(new_challenge, include_structures=True)


# --- ENDPOINT PARA ESTUDIANTES: Ver retos disponibles ---
@router.get("/", response_model=list[ChallengeResponse])
def get_available_challenges(
    dimension: DimensionName | None = None,
    difficulty: DifficultyLevel | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Challenge).filter(
        Challenge.challenge_type.in_([ChallengeType.CLOSED, ChallengeType.SEMI_STRUCTURED])
    )
    if dimension:
        query = query.join(Dimension, Challenge.dimension_id == Dimension.id).filter(
            Dimension.name == dimension
        )
    if difficulty:
        query = query.filter(Challenge.difficulty == difficulty)

    # Nunca se envían correct_answer ni valid_structures a los estudiantes
    return [_to_response(c) for c in query.all()]


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

    grader = get_grader(challenge.challenge_type)
    if grader is None:
        raise HTTPException(
            status_code=400,
            detail="Tipo de reto no soportado en este endpoint (ej. bloques).",
        )
    if (
        challenge.challenge_type == ChallengeType.SEMI_STRUCTURED
        and not challenge.valid_structures
    ):
        raise HTTPException(
            status_code=500,
            detail="El reto semi-estructurado no tiene estructuras válidas definidas.",
        )

    is_correct = grader.grade(submission.submitted_answer, challenge)

    # RN-04: los puntos de un reto solo se otorgan la primera vez que se resuelve
    already_solved = (
        db.query(ChallengeAttempt.id)
        .filter(
            ChallengeAttempt.student_id == current_user.id,
            ChallengeAttempt.challenge_id == challenge_id,
            ChallengeAttempt.is_correct.is_(True),
        )
        .first()
        is not None
    )
    points_earned = challenge.points_reward if (is_correct and not already_solved) else 0

    db.add(
        ChallengeAttempt(
            student_id=current_user.id,
            challenge_id=challenge_id,
            submitted_answer=submission.submitted_answer,
            is_correct=is_correct,
            points_earned=points_earned,
        )
    )

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
    profile.recalculate_level()

    db.commit()

    if is_correct and already_solved:
        feedback = "Correcto, pero ya habías obtenido los puntos de este reto."
    elif is_correct:
        feedback = "¡Excelente! Tu respuesta es correcta."
    else:
        feedback = "Esa no es una respuesta válida. ¡Revisa el problema e inténtalo de nuevo!"

    return AttemptResult(
        is_correct=is_correct,
        points_earned=points_earned,
        total_points=profile.total_points,
        current_level=profile.current_level,
        feedback=feedback,
    )
