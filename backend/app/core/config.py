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

# --- Calificación de imágenes (retos de DFD, PSeInt, Arduino y Scratch) ---
# La clave es opcional para arrancar la API: sin ella, el endpoint de imágenes responde
# 503 y el resto de la plataforma funciona normalmente.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
VISION_MODEL = os.getenv("VISION_MODEL", "claude-sonnet-5-5")
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB por imagen
MAX_IMAGE_ATTEMPTS_PER_DAY = 5  # por estudiante y reto (controla el costo de la IA)
DEFAULT_IMAGE_PASS_SCORE = 70  # porcentaje mínimo de criterios cumplidos
SUPPORTED_IMAGE_LANGUAGES = ("dfd", "pseint", "arduino", "scratch")
