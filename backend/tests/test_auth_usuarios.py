"""Autenticación, registro de usuarios y control de acceso (RNF-02, DoD #9)."""
from datetime import timedelta


from app.models import UserRole
from app.utils.security import create_access_token
from tests.conftest import PASSWORD, crear_usuario, encabezados


def test_registro_de_estudiante_devuelve_201_sin_exponer_el_hash(client):
    r = client.post(
        "/users/",
        json={"email": "nuevo@unipamplona.edu.co", "password": PASSWORD, "full_name": "Nuevo"},
    )
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["role"] == "student"
    assert "password" not in cuerpo and "password_hash" not in cuerpo


def test_registro_con_correo_duplicado_es_rechazado(client):
    datos = {"email": "dup@unipamplona.edu.co", "password": PASSWORD, "full_name": "Dup"}
    assert client.post("/users/", json=datos).status_code == 201
    assert client.post("/users/", json=datos).status_code == 400


def test_registro_con_correo_invalido_devuelve_422(client):
    r = client.post("/users/", json={"email": "no-es-correo", "password": PASSWORD, "full_name": "X"})
    assert r.status_code == 422


def test_login_correcto_devuelve_token_bearer(client, db):
    crear_usuario(db, "ok@unipamplona.edu.co")
    r = client.post("/auth/login", data={"username": "ok@unipamplona.edu.co", "password": PASSWORD})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]


def test_login_con_clave_incorrecta_devuelve_401(client, db):
    crear_usuario(db, "ok@unipamplona.edu.co")
    r = client.post("/auth/login", data={"username": "ok@unipamplona.edu.co", "password": "mala"})
    assert r.status_code == 401


def test_login_de_usuario_inexistente_devuelve_401(client):
    r = client.post("/auth/login", data={"username": "nadie@x.co", "password": "x"})
    assert r.status_code == 401


def test_endpoint_protegido_sin_token_devuelve_401(client):
    assert client.get("/users/me").status_code == 401


def test_endpoint_protegido_con_token_valido_devuelve_el_perfil(client, db):
    crear_usuario(db, "yo@unipamplona.edu.co", nombre="Yo Mismo")
    r = client.get("/users/me", headers=encabezados(client, "yo@unipamplona.edu.co"))
    assert r.status_code == 200
    assert r.json()["email"] == "yo@unipamplona.edu.co"


def test_token_manipulado_devuelve_401(client):
    r = client.get("/users/me", headers={"Authorization": "Bearer token.falso.xyz"})
    assert r.status_code == 401


def test_token_expirado_devuelve_401(client, db):
    crear_usuario(db, "exp@unipamplona.edu.co")
    token = create_access_token({"sub": "exp@unipamplona.edu.co"}, timedelta(seconds=-5))
    r = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_token_de_usuario_eliminado_devuelve_401(client, db):
    token = create_access_token({"sub": "fantasma@unipamplona.edu.co"})
    r = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


# ---------------------------------------------------------------- defectos conocidos
def test_un_anonimo_no_puede_registrarse_como_administrador(client):
    r = client.post(
        "/users/",
        json={
            "email": "intruso@x.co",
            "password": PASSWORD,
            "full_name": "Intruso",
            "role": UserRole.ADMIN.value,
        },
    )
    assert r.status_code in (401, 403) or r.json().get("role") == "student"


def test_listar_usuarios_exige_autenticacion(client, db):
    crear_usuario(db, "privado@unipamplona.edu.co")
    assert client.get("/users/").status_code == 401
