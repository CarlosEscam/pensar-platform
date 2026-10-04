"""Retos cerrados y semi-estructurados, gamificación (RF-02, RF-03, RN-02, RN-03, RN-04)."""
import time

import pytest

from app.models import StudentProfile
from tests.conftest import crear_reto_cerrado, crear_reto_semi

CORRECTA = {"submitted_answer": {"option": "A"}}
INCORRECTA = {"submitted_answer": {"option": "B"}}


def intentar(client, headers, reto_id, cuerpo):
    return client.post(f"/challenges/{reto_id}/attempt", json=cuerpo, headers=headers)


# ------------------------------------------------------------------ RF-03 / RN-03
def test_respuesta_correcta_suma_los_puntos_del_reto(client, db, dimensiones, estudiante):
    reto = crear_reto_cerrado(db, dimensiones["abstraction"], puntos=10)
    r = intentar(client, estudiante, reto, CORRECTA)
    assert r.status_code == 200
    assert r.json()["is_correct"] is True
    assert r.json()["points_earned"] == 10
    assert r.json()["total_points"] == 10
    assert r.json()["current_level"] == 1


def test_respuesta_incorrecta_no_suma_puntos_y_da_retroalimentacion(client, db, dimensiones, estudiante):
    reto = crear_reto_cerrado(db, dimensiones["abstraction"])
    r = intentar(client, estudiante, reto, INCORRECTA)
    assert r.status_code == 200
    assert r.json()["is_correct"] is False
    assert r.json()["points_earned"] == 0
    assert r.json()["feedback"]


def test_el_nivel_sube_al_cruzar_50_puntos_caso_CP_03(client, db, dimensiones, estudiante):
    """CP-03 (FPI-14): de 45 a 55 puntos el nivel pasa de 1 a 2."""
    puntos = [10, 10, 10, 10, 5]  # 45 puntos acumulados, retos distintos
    for i, p in enumerate(puntos):
        reto = crear_reto_cerrado(db, dimensiones["patterns"], titulo=f"R{i}", puntos=p)
        r = intentar(client, estudiante, reto, CORRECTA)
    assert r.json()["total_points"] == 45
    assert r.json()["current_level"] == 1
    ultimo = crear_reto_cerrado(db, dimensiones["patterns"], titulo="R-final", puntos=10)
    r = intentar(client, estudiante, ultimo, CORRECTA)
    assert r.json()["total_points"] == 55
    assert r.json()["current_level"] == 2


@pytest.mark.parametrize("total,nivel", [(0, 1), (49, 1), (50, 2), (99, 2), (100, 3), (149, 3)])
def test_formula_de_nivel_RN_03(client, db, dimensiones, estudiante, total, nivel):
    """nivel = total_puntos // 50 + 1, probado en los valores límite."""
    if total == 0:
        # sin intentos no existe perfil; el nivel inicial documentado es 1
        assert nivel == 1
        return
    reto = crear_reto_cerrado(db, dimensiones["algorithms"], puntos=total)
    r = intentar(client, estudiante, reto, CORRECTA)
    assert r.json()["total_points"] == total
    assert r.json()["current_level"] == nivel


def test_el_perfil_de_gamificacion_se_crea_en_el_primer_intento(client, db, dimensiones, estudiante):
    assert db.query(StudentProfile).count() == 0
    reto = crear_reto_cerrado(db, dimensiones["abstraction"])
    intentar(client, estudiante, reto, CORRECTA)
    db.expire_all()
    assert db.query(StudentProfile).count() == 1


def test_cada_estudiante_acumula_sus_propios_puntos(client, db, dimensiones, estudiante, estudiante2):
    reto = crear_reto_cerrado(db, dimensiones["abstraction"], puntos=20)
    intentar(client, estudiante, reto, CORRECTA)
    r2 = intentar(client, estudiante2, reto, CORRECTA)
    assert r2.json()["total_points"] == 20


# ------------------------------------------------------------------ RN-02 semi-estructurados
def test_estructura_valida_cualquiera_de_las_definidas_es_aceptada(client, db, dimensiones, estudiante):
    reto = crear_reto_semi(db, dimensiones["decomposition"])
    for i, estructura in enumerate(
        [
            {"grupos": {"entrada": ["leer"], "proceso": ["calcular"], "salida": ["mostrar"]}},
            {"grupos": {"datos": ["leer", "calcular"], "resultado": ["mostrar"]}},
        ]
    ):
        r = intentar(client, estudiante, reto, {"submitted_answer": estructura})
        assert r.json()["is_correct"] is True, f"estructura {i} debía ser válida"


def test_el_orden_de_las_claves_json_no_afecta_la_calificacion_RN_02(client, db, dimensiones, estudiante):
    reto = crear_reto_semi(db, dimensiones["decomposition"])
    desordenada = {"grupos": {"salida": ["mostrar"], "proceso": ["calcular"], "entrada": ["leer"]}}
    r = intentar(client, estudiante, reto, {"submitted_answer": desordenada})
    assert r.json()["is_correct"] is True


def test_estructura_que_no_coincide_con_ninguna_es_incorrecta(client, db, dimensiones, estudiante):
    reto = crear_reto_semi(db, dimensiones["decomposition"])
    r = intentar(client, estudiante, reto, {"submitted_answer": {"grupos": {"todo": ["leer"]}}})
    assert r.json()["is_correct"] is False
    assert r.json()["points_earned"] == 0


def test_json_vacio_en_reto_semi_estructurado_es_incorrecto(client, db, dimensiones, estudiante):
    reto = crear_reto_semi(db, dimensiones["decomposition"])
    r = intentar(client, estudiante, reto, {"submitted_answer": {}})
    assert r.status_code == 200
    assert r.json()["is_correct"] is False


# ------------------------------------------------------------------ caminos de V(G)
def test_solo_los_estudiantes_pueden_resolver_retos_camino_1(client, db, dimensiones, docente):
    reto = crear_reto_cerrado(db, dimensiones["abstraction"])
    assert intentar(client, docente, reto, CORRECTA).status_code == 403


def test_reto_inexistente_devuelve_404_camino_2(client, estudiante):
    assert intentar(client, estudiante, 9999, CORRECTA).status_code == 404


def test_intento_sin_token_devuelve_401(client, db, dimensiones):
    reto = crear_reto_cerrado(db, dimensiones["abstraction"])
    r = client.post(f"/challenges/{reto}/attempt", json=CORRECTA)
    assert r.status_code == 401


def test_cuerpo_sin_submitted_answer_devuelve_422(client, db, dimensiones, estudiante):
    reto = crear_reto_cerrado(db, dimensiones["abstraction"])
    assert intentar(client, estudiante, reto, {}).status_code == 422


def test_calificacion_cumple_RNF_01_menos_de_un_segundo(client, db, dimensiones, estudiante):
    reto = crear_reto_cerrado(db, dimensiones["abstraction"])
    t0 = time.perf_counter()
    r = intentar(client, estudiante, reto, CORRECTA)
    assert r.status_code == 200
    assert time.perf_counter() - t0 < 1.0


# ------------------------------------------------------------------ creación de retos
def _cuerpo_reto(dim_id, **extra):
    base = {
        "title": "Nuevo reto",
        "description": "Descripción",
        "dimension_id": dim_id,
        "difficulty": "basic",
        "challenge_type": "closed",
        "content": {"text": "Pregunta", "options": ["A", "B"]},
        "correct_answer": {"option": "A"},
        "points_reward": 10,
    }
    base.update(extra)
    return base


def test_docente_puede_crear_un_reto_cerrado(client, dimensiones, docente):
    r = client.post("/challenges/", json=_cuerpo_reto(dimensiones["abstraction"]), headers=docente)
    assert r.status_code == 201
    assert r.json()["dimension"] == "abstraction"


def test_docente_puede_crear_reto_semi_estructurado_con_dos_estructuras_CP_02(client, dimensiones, docente):
    cuerpo = _cuerpo_reto(
        dimensiones["decomposition"],
        challenge_type="semi_structured",
        correct_answer=None,
        valid_structures=[{"g": ["a"]}, {"g": ["b"]}],
    )
    assert client.post("/challenges/", json=cuerpo, headers=docente).status_code == 201


def test_estudiante_no_puede_crear_retos(client, dimensiones, estudiante):
    r = client.post("/challenges/", json=_cuerpo_reto(dimensiones["abstraction"]), headers=estudiante)
    assert r.status_code == 403


def test_listado_de_retos_exige_autenticacion(client):
    assert client.get("/challenges/").status_code == 401


def test_listado_no_expone_la_respuesta_correcta(client, db, dimensiones, estudiante):
    crear_reto_cerrado(db, dimensiones["abstraction"])
    cuerpo = client.get("/challenges/", headers=estudiante).json()
    assert len(cuerpo) == 1
    assert "correct_answer" not in cuerpo[0]


# ------------------------------------------------------------------ defectos conocidos
@pytest.mark.xfail(strict=True, reason="BUG-03: RN-04 no implementada, repetir el mismo reto suma puntos infinitos")
def test_repetir_un_reto_cerrado_no_suma_puntos_RN_04(client, db, dimensiones, estudiante):
    reto = crear_reto_cerrado(db, dimensiones["abstraction"], puntos=10)
    intentar(client, estudiante, reto, CORRECTA)
    r = intentar(client, estudiante, reto, CORRECTA)
    assert r.json()["points_earned"] == 0
    assert r.json()["total_points"] == 10


@pytest.mark.xfail(strict=True, reason="BUG-04: GET /challenges/ solo lista retos cerrados; los semi-estructurados no se descubren")
def test_el_listado_incluye_retos_semi_estructurados(client, db, dimensiones, estudiante):
    crear_reto_semi(db, dimensiones["decomposition"])
    tipos = {c["challenge_type"] for c in client.get("/challenges/", headers=estudiante).json()}
    assert "semi_structured" in tipos


@pytest.mark.xfail(strict=True, reason="BUG-05: el filtro ?dimension= del listado se ignora")
def test_el_filtro_por_dimension_funciona(client, db, dimensiones, estudiante):
    crear_reto_cerrado(db, dimensiones["abstraction"], titulo="A")
    crear_reto_cerrado(db, dimensiones["patterns"], titulo="P")
    cuerpo = client.get("/challenges/?dimension=abstraction", headers=estudiante).json()
    assert [c["dimension"] for c in cuerpo] == ["abstraction"]


@pytest.mark.xfail(strict=True, reason="BUG-06: se crea un reto semi-estructurado con < 2 estructuras (RF-02 exige HTTP 400)")
def test_reto_semi_con_una_sola_estructura_es_rechazado_RF_02(client, dimensiones, docente):
    cuerpo = _cuerpo_reto(
        dimensiones["decomposition"],
        challenge_type="semi_structured",
        correct_answer=None,
        valid_structures=[{"g": ["a"]}],
    )
    assert client.post("/challenges/", json=cuerpo, headers=docente).status_code == 400


@pytest.mark.xfail(strict=True, reason="BUG-07: la creación de retos no valida tipo, dimensión ni datos y falla con HTTP 500")
@pytest.mark.parametrize(
    "extra",
    [{"challenge_type": "tipo-inventado"}, {"difficulty": "imposible"}, {"dimension_id": 9999}],
)
def test_creacion_de_reto_con_datos_invalidos_no_produce_500(client, dimensiones, docente, extra):
    cuerpo = _cuerpo_reto(dimensiones["abstraction"], **extra)
    try:
        r = client.post("/challenges/", json=cuerpo, headers=docente)
    except Exception:  # la excepción no controlada llega al cliente de pruebas
        pytest.fail("error no controlado (equivale a HTTP 500)")
    assert r.status_code in (400, 404, 422)


@pytest.mark.xfail(strict=True, reason="BUG-08: el diseño documentado (recalculate_level y constantes en config) no existe en el código")
def test_el_diseno_documentado_en_fpi_11_y_fpi_12_existe_en_el_codigo():
    from app.core import config

    assert hasattr(StudentProfile, "recalculate_level")
    assert config.POINTS_PER_LEVEL == 50
    assert config.TOTAL_DIAGNOSTIC_QUESTIONS == 28
