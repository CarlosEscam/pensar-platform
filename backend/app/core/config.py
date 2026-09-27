import os
from dotenv import load_dotenv

load_dotenv()

# Clave secreta para firmar los JWT
SECRET_KEY = os.getenv("SECRET_KEY", "clave_por_defecto")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # El token dura 24 horas
