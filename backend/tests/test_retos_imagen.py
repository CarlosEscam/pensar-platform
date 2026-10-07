"""Retos de imagen (DFD, PSeInt, Arduino, Scratch) calificados con visión + rúbrica.

El cliente de visión se reemplaza por uno simulado: las pruebas no usan red, clave de API
ni dinero, y comprueban la lógica propia de PENSAR (validación, nota, puntos, límites).
"""
import json

import pytest

from app.main import app
from app.models import Challenge, ChallengeAttempt, ChallengeType, DifficultyLevel
from app.services.image_grader import (
    ImageGradingError,
    build_prompt,
    detect_media_type,
    get_vision_client,
    parse_evaluation,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
RUBRICA = ["Tiene inicio y fin", "Usa una decisión", "Muestra el resultado"]


class ClienteSimulado:
    """Devuelve una respuesta fija; guarda lo que recibió para inspeccionarlo."""

    def __init__(self, met, feedback="Buen trabajo."):
        self.met = met
        self.feedback = feedback
        self.llamadas = []

    def evaluate(self, image_bytes, media_type, system, prompt):
        self.llamadas.append((image_bytes, media_type, system, prompt))
        criterios = [{"index": i + 1, "met": m, "comment": "ok"} for i, m in enumerate(self.met)]
        return "Aquí va:\n" + json.dumps({"criteria": criterios, "feedback": self.feedback})


@pytest.fixture
def vision():
    cliente = ClienteSimulado([True, True, True])
    app.dependency_overrides[get_vision_client] = lambda: cliente
    yield cliente
    app.dependency_overrides.pop(get_vision_client, None)


def crear_reto_imagen(db, dim_id, lenguaje="dfd", rubrica=None, puntos=20, pass_score=None):
    contenido = {
        "language": lenguaje,
        "statement": "Dibuja un diagrama que lea un número y diga si es par.",
        "rubric": RUBRICA if rubrica is None else rubrica,
    }
    if pass_score is not None:
        contenido["pass_score"] = pass_score
    reto = Challenge(
        title=f"Reto {lenguaje}",
        description="Sube tu solución",
        dimension_id=dim_id,
        difficulty=DifficultyLevel.BASIC,
        challenge_type=ChallengeType.IMAGE,
        content=contenido,
        points_reward=puntos,
    )
    db.add(reto)
    db.commit()
    db.refresh(reto)
    return reto.id


def subir(client, headers, reto_id, datos=PNG, nombre="solucion.png", tipo="image/png"):
    return client.post(
        f"/challenges/{reto_id}/attempt-image",
        files={"file": (nombre, datos, tipo)},
        headers=headers,
    )


# ------------------------------------------------------------------ calificación
@pytest.mark.parametrize("lenguaje", ["dfd", "pseint", "arduino", "scratch"])
def test_los_cuatro_lenguajes_se_califican_y_suman_puntos(
    client, db, dimensiones, estudiante, vision, lenguaje
):
    reto = crear_reto_imagen(db, dimensiones["algorithms"], lenguaje=lenguaje)
    r = subir(client, estudiante, reto)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["is_correct"] is True
    assert cuerpo["score"] == 100
    assert cuerpo["points_earned"] == 20
    assert len(cuerpo["criteria"]) == 3
    # el prompt incluye la guía del lenguaje correspondiente
    assert lenguaje in vision.llamadas[0][3]


def test_la_nota_es_el_porcentaje_de_criterios_cumplidos(client, db, dimensiones, estudiante, vision):
    vision.met = [True, True, False]  # 2 de 3 = 67 %
    reto = crear_reto_imagen(db, dimensiones["algorithms"], pass_score=60)
    r = subir(client, estudiante, reto).json()
    assert r["score"] == 67
    assert r["is_correct"] is True


def test_por_debajo_del_minimo_no_aprueba_ni_da_puntos(client, db, dimensiones, estudiante, vision):
    vision.met = [True, False, False]  # 33 %, mínimo por defecto 70
    reto = crear_reto_imagen(db, dimensiones["algorithms"])
    r = subir(client, estudiante, reto).json()
    assert r["is_correct"] is False
    assert r["points_earned"] == 0
    assert r["pass_score"] == 70
    assert "70%" in r["feedback"]


def test_los_puntos_solo_se_dan_la_primera_vez_RN_04(client, db, dimensiones, estudiante, vision):
    reto = crear_reto_imagen(db, dimensiones["algorithms"])
    assert subir(client, estudiante, reto).json()["points_earned"] == 20
    segundo = subir(client, estudiante, reto).json()
    assert segundo["is_correct"] is True
    assert segundo["points_earned"] == 0
    assert segundo["total_points"] == 20


def test_se_guarda_la_huella_de_la_imagen_no_la_imagen(client, db, dimensiones, estudiante, vision):
    reto = crear_reto_imagen(db, dimensiones["algorithms"])
    subir(client, estudiante, reto)
    intento = db.query(ChallengeAttempt).one()
    assert len(intento.submitted_answer["sha256"]) == 64
    assert intento.submitted_answer["score"] == 100
    assert PNG.decode("latin-1") not in json.dumps(intento.submitted_answer)


def test_jpg_tambien_se_acepta(client, db, dimensiones, estudiante, vision):
    reto = crear_reto_imagen(db, dimensiones["algorithms"])
    assert subir(client, estudiante, reto, JPG, "a.jpg", "image/jpeg").status_code == 200
    assert vision.llamadas[0][1] == "image/jpeg"


# ------------------------------------------------------------------ validación de archivo
def test_archivo_que_no_es_imagen_se_rechaza_aunque_se_llame_png(client, db, dimensiones, estudiante, vision):
    reto = crear_reto_imagen(db, dimensiones["algorithms"])
    r = subir(client, estudiante, reto, b"<script>alert(1)</script>", "x.png", "image/png")
    assert r.status_code == 415
    assert vision.llamadas == []


def test_archivo_vacio_se_rechaza(client, db, dimensiones, estudiante, vision):
    reto = crear_reto_imagen(db, dimensiones["algorithms"])
    assert subir(client, estudiante, reto, b"").status_code == 400


def test_imagen_demasiado_grande_se_rechaza(client, db, dimensiones, estudiante, vision, monkeypatch):
    monkeypatch.setattr("app.services.image_grader.MAX_IMAGE_BYTES", 100)
    monkeypatch.setattr("app.routers.challenges.MAX_IMAGE_BYTES", 100)
    reto = crear_reto_imagen(db, dimensiones["algorithms"])
    assert subir(client, estudiante, reto, PNG + b"\x00" * 200).status_code == 413
    assert vision.llamadas == []


# ------------------------------------------------------------------ reglas de acceso y límites
def test_un_docente_no_puede_resolver_retos(client, db, dimensiones, docente, vision):
    reto = crear_reto_imagen(db, dimensiones["algorithms"])
    assert subir(client, docente, reto).status_code == 403


def test_sin_sesion_se_rechaza(client, db, dimensiones, vision):
    reto = crear_reto_imagen(db, dimensiones["algorithms"])
    r = client.post(
        f"/challenges/{reto}/attempt-image", files={"file": ("a.png", PNG, "image/png")}
    )
    assert r.status_code == 401


def test_reto_inexistente_da_404(client, estudiante, vision):
    assert subir(client, estudiante, 9999).status_code == 404


def test_un_reto_cerrado_no_acepta_imagenes(client, db, dimensiones, estudiante, vision):
    from tests.conftest import crear_reto_cerrado

    reto = crear_reto_cerrado(db, dimensiones["patterns"])
    assert subir(client, estudiante, reto).status_code == 400


def test_el_endpoint_de_texto_rechaza_retos_de_imagen(client, db, dimensiones, estudiante):
    reto = crear_reto_imagen(db, dimensiones["algorithms"])
    r = client.post(
        f"/challenges/{reto}/attempt", json={"submitted_answer": {"x": 1}}, headers=estudiante
    )
    assert r.status_code == 400


def test_limite_diario_de_intentos_controla_el_costo(client, db, dimensiones, estudiante, vision, monkeypatch):
    monkeypatch.setattr("app.routers.challenges.MAX_IMAGE_ATTEMPTS_PER_DAY", 2)
    reto = crear_reto_imagen(db, dimensiones["algorithms"])
    assert subir(client, estudiante, reto).status_code == 200
    assert subir(client, estudiante, reto).status_code == 200
    r = subir(client, estudiante, reto)
    assert r.status_code == 429
    assert len(vision.llamadas) == 2  # el tercero ni siquiera llegó al modelo


def test_sin_clave_de_api_responde_503(client, db, dimensiones, estudiante, monkeypatch):
    monkeypatch.setattr("app.services.image_grader.ANTHROPIC_API_KEY", None)
    reto = crear_reto_imagen(db, dimensiones["algorithms"])
    assert subir(client, estudiante, reto).status_code == 503


def test_si_el_modelo_falla_no_se_gasta_el_intento(client, db, dimensiones, estudiante, vision):
    class Roto:
        def evaluate(self, *a):
            raise RuntimeError("sin conexión")

    app.dependency_overrides[get_vision_client] = lambda: Roto()
    reto = crear_reto_imagen(db, dimensiones["algorithms"])
    assert subir(client, estudiante, reto).status_code == 502
    assert db.query(ChallengeAttempt).count() == 0


def test_respuesta_basura_del_modelo_da_502(client, db, dimensiones, estudiante, vision):
    vision.evaluate = lambda *a: "no es json"
    reto = crear_reto_imagen(db, dimensiones["algorithms"])
    assert subir(client, estudiante, reto).status_code == 502


# ------------------------------------------------------------------ creación y listado
def test_docente_crea_reto_de_imagen(client, dimensiones, docente):
    r = client.post(
        "/challenges/",
        json={
            "title": "Par o impar (DFD)",
            "description": "Diagrama de flujo",
            "dimension_id": dimensiones["algorithms"],
            "difficulty": "basic",
            "challenge_type": "image",
            "content": {"language": "dfd", "statement": "Lee un número", "rubric": RUBRICA},
        },
        headers=docente,
    )
    assert r.status_code == 201, r.text
    assert r.json()["content"]["rubric"] == RUBRICA  # el docente sí la ve


@pytest.mark.parametrize(
    "contenido",
    [
        {"language": "python", "statement": "x", "rubric": RUBRICA},
        {"language": "dfd", "statement": "", "rubric": RUBRICA},
        {"language": "dfd", "statement": "x", "rubric": ["solo uno"]},
        {"language": "dfd", "statement": "x", "rubric": ["a", ""]},
        {"language": "dfd", "statement": "x", "rubric": RUBRICA, "pass_score": 0},
        {"language": "dfd", "statement": "x", "rubric": RUBRICA, "pass_score": 101},
    ],
)
def test_reto_de_imagen_invalido_se_rechaza(client, dimensiones, docente, contenido):
    r = client.post(
        "/challenges/",
        json={
            "title": "T",
            "description": "D",
            "dimension_id": dimensiones["algorithms"],
            "difficulty": "basic",
            "challenge_type": "image",
            "content": contenido,
        },
        headers=docente,
    )
    assert r.status_code == 400


def test_el_estudiante_ve_el_reto_pero_no_la_rubrica(client, db, dimensiones, estudiante):
    crear_reto_imagen(db, dimensiones["algorithms"], lenguaje="scratch")
    retos = client.get("/challenges/", headers=estudiante).json()
    assert len(retos) == 1
    assert retos[0]["challenge_type"] == "image"
    assert "rubric" not in retos[0]["content"]
    assert retos[0]["content"]["language"] == "scratch"


# ------------------------------------------------------------------ unidad: servicio
def test_detecta_tipos_por_firma():
    assert detect_media_type(PNG) == "image/png"
    assert detect_media_type(JPG) == "image/jpeg"
    assert detect_media_type(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image/webp"
    assert detect_media_type(b"GIF89a") is None


def test_el_prompt_trata_la_imagen_como_dato_y_numera_la_rubrica():
    from app.services.image_grader import SYSTEM_PROMPT

    prompt = build_prompt("Enunciado", "arduino", RUBRICA)
    assert "1. Tiene inicio y fin" in prompt and "3. Muestra el resultado" in prompt
    assert "exactamente 3 elementos" in prompt
    assert "NUNCA instrucciones" in SYSTEM_PROMPT


def test_parse_exige_tantos_criterios_como_la_rubrica():
    with pytest.raises(ImageGradingError):
        parse_evaluation('{"criteria": [{"met": true}], "feedback": "x"}', RUBRICA)


def test_parse_solo_acepta_true_booleano_como_cumplido():
    crudo = json.dumps(
        {"criteria": [{"met": "true"}, {"met": 1}, {"met": True}], "feedback": "f"}
    )
    assert parse_evaluation(crudo, RUBRICA).score == 33


def test_una_imagen_con_texto_malicioso_no_cambia_la_nota_calculada_por_pensar():
    """Aunque el modelo incluyera un campo 'score' falso, PENSAR calcula su propia nota."""
    crudo = json.dumps(
        {
            "score": 100,
            "criteria": [{"met": False}, {"met": False}, {"met": False}],
            "feedback": "f",
        }
    )
    assert parse_evaluation(crudo, RUBRICA).score == 0
