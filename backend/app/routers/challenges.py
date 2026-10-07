import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from ..core.config import (
    DEFAULT_IMAGE_PASS_SCORE,
    MAX_IMAGE_ATTEMPTS_PER_DAY,
    MAX_IMAGE_BYTES,
    SUPPORTED_IMAGE_LANGUAGES,
)
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
    ImageAttemptResult,
)
from ..services.graders import get_grader
from ..services.image_grader import (
    ImageGradingError,
    VisionClient,
    get_vision_client,
    grade_image,
    validate_image,
)
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
    if c.challenge_type == ChallengeType.IMAGE and not include_structures:
        # La rúbrica es material del docente: el estudiante no la recibe.
        data["content"] = {k: v for k, v in c.content.items() if k != "rubric"}
    if include_structures:
        data["valid_structures"] = c.valid_structures
    return data


def _validate_image_content(content: dict) -> None:
    """Un reto de imagen exige lenguaje soportado, enunciado y una rúbrica de 2+ criterios."""
    if content.get("language") not in SUPPORTED_IMAGE_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"content.language debe ser uno de: {', '.join(SUPPORTED_IMAGE_LANGUAGES)}.",
        )
    statement = content.get("statement")
    if not isinstance(statement, str) or not statement.strip():
        raise HTTPException(status_code=400, detail="content.statement es obligatorio.")
    rubric = content.get("rubric")
    if (
        not isinstance(rubric, list)
        or len(rubric) < 2
        or not all(isinstance(c, str) and c.strip() for c in rubric)
    ):
        raise HTTPException(
            status_code=400,
            detail="content.rubric debe ser una lista de al menos 2 criterios (texto).",
        )
    pass_score = content.get("pass_score", DEFAULT_IMAGE_PASS_SCORE)
    if isinstance(pass_score, bool) or not isinstance(pass_score, int) or not 1 <= pass_score <= 100:
        raise HTTPException(
            status_code=400, detail="content.pass_score debe ser un entero entre 1 y 100."
        )


def _register_attempt(
    db: Session,
    user: User,
    challenge: Challenge,
    submitted_answer: dict,
    is_correct: bool,
) -> tuple[int, bool, StudentProfile]:
    """Guarda el intento y aplica RN-03/RN-04. Devuelve (puntos, ya_resuelto, perfil)."""
    # RN-04: los puntos de un reto solo se otorgan la primera vez que se resuelve
    already_solved = (
        db.query(ChallengeAttempt.id)
        .filter(
            ChallengeAttempt.student_id == user.id,
            ChallengeAttempt.challenge_id == challenge.id,
            ChallengeAttempt.is_correct.is_(True),
        )
        .first()
        is not None
    )
    points_earned = challenge.points_reward if (is_correct and not already_solved) else 0

    db.add(
        ChallengeAttempt(
            student_id=user.id,
            challenge_id=challenge.id,
            submitted_answer=submitted_answer,
            is_correct=is_correct,
            points_earned=points_earned,
        )
    )

    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    if not profile:
        profile = StudentProfile(
            user_id=user.id, total_points=0, current_level=1, current_streak=0
        )
        db.add(profile)

    profile.total_points += points_earned
    profile.recalculate_level()

    db.commit()
    return points_earned, already_solved, profile


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
    elif challenge_data.challenge_type == ChallengeType.IMAGE:
        _validate_image_content(challenge_data.content)

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
        Challenge.challenge_type.in_(
            [ChallengeType.CLOSED, ChallengeType.SEMI_STRUCTURED, ChallengeType.IMAGE]
        )
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
            detail="Tipo de reto no soportado en este endpoint (los retos de imagen usan /attempt-image).",
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

    points_earned, already_solved, profile = _register_attempt(
        db, current_user, challenge, submission.submitted_answer, is_correct
    )

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


# --- ENDPOINT PARA ESTUDIANTES: Resolver un reto subiendo una imagen ---
@router.post("/{challenge_id}/attempt-image", response_model=ImageAttemptResult)
def submit_image_attempt(
    challenge_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    vision: VisionClient = Depends(get_vision_client),
):
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=403, detail="Solo los estudiantes pueden resolver retos."
        )

    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Reto no encontrado.")
    if challenge.challenge_type != ChallengeType.IMAGE:
        raise HTTPException(status_code=400, detail="Este reto no recibe imágenes.")

    # Se lee un byte más del máximo para detectar archivos demasiado grandes sin cargarlos enteros.
    data = file.file.read(MAX_IMAGE_BYTES + 1)
    media_type = validate_image(data)

    # Control de costo: máximo de calificaciones por estudiante, reto y día.
    since = datetime.now(timezone.utc) - timedelta(days=1)
    recent = (
        db.query(ChallengeAttempt.id)
        .filter(
            ChallengeAttempt.student_id == current_user.id,
            ChallengeAttempt.challenge_id == challenge_id,
            ChallengeAttempt.created_at >= since,
        )
        .count()
    )
    if recent >= MAX_IMAGE_ATTEMPTS_PER_DAY:
        raise HTTPException(
            status_code=429,
            detail=f"Alcanzaste el máximo de {MAX_IMAGE_ATTEMPTS_PER_DAY} intentos de este reto por día.",
        )

    try:
        grade = grade_image(vision, data, media_type, challenge.content)
    except ImageGradingError:
        # No se registra intento: un fallo del servicio no debe gastar el cupo del estudiante.
        raise HTTPException(
            status_code=502,
            detail="No se pudo calificar la imagen en este momento. Inténtalo de nuevo.",
        )

    pass_score = challenge.content.get("pass_score", DEFAULT_IMAGE_PASS_SCORE)
    is_correct = grade.score >= pass_score

    criteria = [
        {"criterion": c.criterion, "met": c.met, "comment": c.comment} for c in grade.criteria
    ]
    # Se guarda el resultado y la huella de la imagen, no la imagen (privacidad y espacio).
    submitted = {
        "language": challenge.content["language"],
        "filename": (file.filename or "")[:120],
        "sha256": hashlib.sha256(data).hexdigest(),
        "score": grade.score,
        "criteria": criteria,
    }
    points_earned, already_solved, profile = _register_attempt(
        db, current_user, challenge, submitted, is_correct
    )

    if is_correct and already_solved:
        prefix = "Aprobado, pero ya habías obtenido los puntos de este reto."
    elif is_correct:
        prefix = "¡Excelente! Tu entrega cumple lo pedido."
    else:
        prefix = f"Aún no llegas al {pass_score}% requerido. ¡Corrige y vuelve a subirla!"
    feedback = f"{prefix} {grade.feedback}".strip()

    return ImageAttemptResult(
        is_correct=is_correct,
        points_earned=points_earned,
        total_points=profile.total_points,
        current_level=profile.current_level,
        feedback=feedback,
        score=grade.score,
        pass_score=pass_score,
        criteria=criteria,
    )
