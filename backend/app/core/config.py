import os

from dotenv import load_dotenv

load_dotenv()

# Clave secreta para firmar los JWT. Es obligatoria: sin ella la aplicación no arranca,
# en lugar de usar un valor por defecto conocido públicamente (BUG-13).
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "Falta la variable de entorno SECRET_KEY. Defínela en backend/.env (no versionado) "
        "o como secreto del entorno de despliegue."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # El token dura 24 horas

# Constantes de negocio (antes eran "números mágicos" dispersos en los routers)
POINTS_PER_LEVEL = 50  # RN-03: nivel = total_points // POINTS_PER_LEVEL + 1
TOTAL_DIAGNOSTIC_QUESTIONS = 28  # RF-01: 28 ítems del TPC
MAX_DIAGNOSTIC_ATTEMPTS = 1  # RN-01: un diagnóstico por periodo académico
