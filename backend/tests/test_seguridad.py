"""RNF-02: contraseñas con bcrypt (costo >= 10) y tokens JWT firmados."""
from datetime import timedelta

import jwt
import pytest

from app.core.config import ALGORITHM, SECRET_KEY
from app.utils.security import create_access_token, hash_password, verify_password


def test_la_contrasena_no_se_guarda_en_texto_plano():
    hashed = hash_password("MiClave123")
    assert hashed != "MiClave123"
    assert "MiClave123" not in hashed


def test_hash_usa_bcrypt_con_costo_minimo_10():
    hashed = hash_password("MiClave123")
    assert hashed.startswith("$2b$")
    costo = int(hashed.split("$")[2])
    assert costo >= 10  # RNF-02


def test_verify_password_acepta_la_correcta_y_rechaza_la_incorrecta():
    hashed = hash_password("MiClave123")
    assert verify_password("MiClave123", hashed) is True
    assert verify_password("otra-clave", hashed) is False


def test_dos_hashes_de_la_misma_clave_son_distintos_por_la_sal():
    assert hash_password("igual") != hash_password("igual")


def test_token_contiene_sub_y_expiracion_y_se_firma_con_la_clave():
    token = create_access_token({"sub": "a@b.co"}, timedelta(minutes=5))
    datos = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert datos["sub"] == "a@b.co"
    assert "exp" in datos


def test_token_firmado_con_otra_clave_es_rechazado():
    token = jwt.encode({"sub": "a@b.co"}, "otra-clave-distinta-0123456789abcdef", algorithm=ALGORITHM)
    with pytest.raises(jwt.InvalidTokenError):
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def test_la_aplicacion_no_arranca_sin_secret_key():
    import os
    import subprocess
    import sys

    entorno = {**os.environ, "SECRET_KEY": ""}  # clave vacía = no configurada
    proceso = subprocess.run(
        [sys.executable, "-c", "import app.core.config"],
        env=entorno, capture_output=True, text=True,
    )
    assert proceso.returncode != 0
