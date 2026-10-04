from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.user import User, UserRole
from ..schemas.user import UserCreate, UserResponse
from ..utils.security import hash_password
from ..utils.jwt import get_current_user, get_optional_user, require_roles

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    """
    Registra un nuevo usuario. El autorregistro solo crea estudiantes; para crear
    docentes o administradores se requiere un administrador autenticado (BUG-01).
    """
    if user_data.role != UserRole.STUDENT and (
        current_user is None or current_user.role != UserRole.ADMIN
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un administrador puede crear docentes o administradores.",
        )
    # Verificar si el email ya existe
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo electrónico ya está registrado",
        )

    # Crear el nuevo usuario con contraseña encriptada
    new_user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role,
    )

    # Guardar en la base de datos
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.get("/", response_model=list[UserResponse])
def get_users(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
):
    """
    Obtiene una lista de usuarios (con paginación). Solo docentes y administradores (BUG-02).
    """
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Obtiene el perfil del usuario autenticado.
    Solo accesible con un token JWT válido.
    """
    return current_user
