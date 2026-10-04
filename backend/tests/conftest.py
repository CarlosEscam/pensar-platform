"""Configuración común de la suite de pruebas de PENSAR.

- Usa una base SQLite temporal (no requiere PostgreSQL ni Docker).
- Las variables de entorno se fijan ANTES de importar la aplicación, de modo que
  nunca se usan credenciales reales ni el archivo .env del desarrollador.
- Los usuarios y datos semilla se crean directamente en la base de datos para que
  las pruebas no dependan de endpoints que pueden cambiar (p. ej. /diagnostic/seed).
"""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="pensar_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["SECRET_KEY"] = "clave-solo-para-pruebas-automatizadas-0123456789abcdef"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Challenge,
    ChallengeType,
    DiagnosticQuestion,
    DifficultyLevel,
    Dimension,
    User,
    UserRole,
)
from app.models.diagnostic import DimensionName, QuestionType  # noqa: E402
from app.utils.security import hash_password  # noqa: E402

PASSWORD = "Clave-Segura-123"


@pytest.fixture(autouse=True)
def base_de_datos_limpia():
    """Cada prueba arranca con tablas vacías (aislamiento total)."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    sesion = SessionLocal()
    try:
        yield sesion
    finally:
        sesion.close()


def crear_usuario(db, email, role=UserRole.STUDENT, nombre="Usuario de Prueba"):
    usuario = User(
        email=email, password_hash=hash_password(PASSWORD), full_name=nombre, role=role
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def encabezados(client, email):
    """Inicia sesión por la API real y devuelve el encabezado Authorization."""
    r = client.post("/auth/login", data={"username": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def estudiante(db, client):
    crear_usuario(db, "estudiante@unipamplona.edu.co", UserRole.STUDENT, "Estudiante Uno")
    return encabezados(client, "estudiante@unipamplona.edu.co")


@pytest.fixture
def estudiante2(db, client):
    crear_usuario(db, "estudiante2@unipamplona.edu.co", UserRole.STUDENT, "Estudiante Dos")
    return encabezados(client, "estudiante2@unipamplona.edu.co")


@pytest.fixture
def docente(db, client):
    crear_usuario(db, "docente@unipamplona.edu.co", UserRole.TEACHER, "Docente Titular")
    return encabezados(client, "docente@unipamplona.edu.co")


@pytest.fixture
def dimensiones(db):
    """Las 4 dimensiones del pensamiento computacional (TPC)."""
    for nombre in DimensionName:
        db.add(Dimension(name=nombre))
    db.commit()
    return {d.name.value: d.id for d in db.query(Dimension).all()}


@pytest.fixture
def diagnostico_28(db, dimensiones):
    """28 ítems (7 por dimensión), respuesta correcta {"correct": "A"}."""
    for nombre, dim_id in dimensiones.items():
        for i in range(7):
            db.add(
                DiagnosticQuestion(
                    dimension_id=dim_id,
                    question_type=QuestionType.MULTIPLE_CHOICE,
                    content={"text": f"{nombre} #{i + 1}", "options": ["A", "B", "C"]},
                    correct_answer={"correct": "A"},
                    points=1,
                )
            )
    db.commit()
    return [q.id for q in db.query(DiagnosticQuestion).order_by(DiagnosticQuestion.id).all()]


def crear_reto_cerrado(db, dim_id, titulo="Reto cerrado", puntos=10, correcta=None):
    reto = Challenge(
        title=titulo,
        description="Descripción del reto",
        dimension_id=dim_id,
        difficulty=DifficultyLevel.BASIC,
        challenge_type=ChallengeType.CLOSED,
        content={"text": "¿Cuál es el siguiente patrón?", "options": ["A", "B"]},
        correct_answer=correcta or {"option": "A"},
        points_reward=puntos,
    )
    db.add(reto)
    db.commit()
    db.refresh(reto)
    return reto.id


ESTRUCTURAS = [
    {"grupos": {"entrada": ["leer"], "proceso": ["calcular"], "salida": ["mostrar"]}},
    {"grupos": {"datos": ["leer", "calcular"], "resultado": ["mostrar"]}},
]


def crear_reto_semi(db, dim_id, titulo="Reto semi", puntos=15, estructuras=None):
    reto = Challenge(
        title=titulo,
        description="Divide el problema en subproblemas",
        dimension_id=dim_id,
        difficulty=DifficultyLevel.INTERMEDIATE,
        challenge_type=ChallengeType.SEMI_STRUCTURED,
        content={"text": "Descompón el problema", "items": ["leer", "calcular", "mostrar"]},
        valid_structures=ESTRUCTURAS if estructuras is None else estructuras,
        points_reward=puntos,
    )
    db.add(reto)
    db.commit()
    db.refresh(reto)
    return reto.id
