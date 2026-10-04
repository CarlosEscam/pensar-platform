"""Diagnóstico inicial TPC (RF-01, RN-01, CP-01)."""
import time


RESPUESTA_OK = {"correct": "A"}
RESPUESTA_MAL = {"correct": "C"}


def iniciar(client, headers):
    return client.post("/diagnostic/attempts", headers=headers)


def enviar(client, headers, attempt_id, respuestas):
    cuerpo = {"answers": [{"question_id": q, "student_answer": a} for q, a in respuestas]}
    return client.post(f"/diagnostic/attempts/{attempt_id}/submit", json=cuerpo, headers=headers)


def test_preguntas_exigen_autenticacion(client):
    assert client.get("/diagnostic/questions").status_code == 401


def test_las_preguntas_no_exponen_la_respuesta_correcta(client, estudiante, diagnostico_28):
    preguntas = client.get("/diagnostic/questions", headers=estudiante).json()
    assert len(preguntas) == 28
    assert all("correct_answer" not in p for p in preguntas)


def test_el_diagnostico_cubre_las_4_dimensiones_con_7_items_cada_una(client, estudiante, diagnostico_28):
    preguntas = client.get("/diagnostic/questions", headers=estudiante).json()
    por_dim = {}
    for p in preguntas:
        por_dim[p["dimension"]] = por_dim.get(p["dimension"], 0) + 1
    assert por_dim == {"abstraction": 7, "decomposition": 7, "patterns": 7, "algorithms": 7}


def test_solo_estudiantes_inician_el_diagnostico(client, docente):
    assert iniciar(client, docente).status_code == 403


def test_calificacion_por_dimension_caso_CP_01(client, estudiante, diagnostico_28):
    """CP-01 (FPI-14): 28 respuestas, puntaje desglosado por dimensión en < 3 s."""
    attempt_id = iniciar(client, estudiante).json()["attempt_id"]
    t0 = time.perf_counter()
    r = enviar(client, estudiante, attempt_id, [(q, RESPUESTA_OK) for q in diagnostico_28])
    assert time.perf_counter() - t0 < 3.0
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["total_score"] == 28
    assert cuerpo["max_score"] == 28
    assert {d["dimension"] for d in cuerpo["scores_by_dimension"]} == {
        "abstraction", "decomposition", "patterns", "algorithms",
    }
    assert all(d["score"] == 7 and d["max_score"] == 7 for d in cuerpo["scores_by_dimension"])


def test_puntaje_parcial_se_calcula_correctamente(client, estudiante, diagnostico_28):
    attempt_id = iniciar(client, estudiante).json()["attempt_id"]
    respuestas = [(q, RESPUESTA_OK if i < 10 else RESPUESTA_MAL) for i, q in enumerate(diagnostico_28)]
    assert enviar(client, estudiante, attempt_id, respuestas).json()["total_score"] == 10


def test_no_se_puede_enviar_dos_veces_el_mismo_intento(client, estudiante, diagnostico_28):
    attempt_id = iniciar(client, estudiante).json()["attempt_id"]
    assert enviar(client, estudiante, attempt_id, [(diagnostico_28[0], RESPUESTA_OK)]).status_code == 200
    assert enviar(client, estudiante, attempt_id, [(diagnostico_28[0], RESPUESTA_OK)]).status_code == 400


def test_un_estudiante_no_puede_enviar_el_intento_de_otro(client, estudiante, estudiante2, diagnostico_28):
    attempt_id = iniciar(client, estudiante).json()["attempt_id"]
    r = enviar(client, estudiante2, attempt_id, [(diagnostico_28[0], RESPUESTA_OK)])
    assert r.status_code == 404


def test_tras_completar_no_se_puede_iniciar_otro_diagnostico_RN_01(client, estudiante, diagnostico_28):
    attempt_id = iniciar(client, estudiante).json()["attempt_id"]
    enviar(client, estudiante, attempt_id, [(diagnostico_28[0], RESPUESTA_OK)])
    r = iniciar(client, estudiante)
    assert r.status_code >= 400  # bloqueado (el código exacto se evalúa en BUG-10)


def test_intento_inexistente_devuelve_404(client, estudiante):
    assert enviar(client, estudiante, 9999, []).status_code == 404


# ------------------------------------------------------------------ defectos conocidos
def test_respuestas_duplicadas_no_inflan_el_puntaje(client, estudiante, diagnostico_28):
    attempt_id = iniciar(client, estudiante).json()["attempt_id"]
    q = diagnostico_28[0]
    r = enviar(client, estudiante, attempt_id, [(q, RESPUESTA_OK)] * 10)
    assert r.status_code >= 400 or r.json()["total_score"] <= 1


def test_rn_01_responde_409_conflict(client, estudiante, diagnostico_28):
    attempt_id = iniciar(client, estudiante).json()["attempt_id"]
    enviar(client, estudiante, attempt_id, [(diagnostico_28[0], RESPUESTA_OK)])
    assert iniciar(client, estudiante).status_code == 409


def test_el_endpoint_seed_exige_autenticacion(client):
    assert client.post("/diagnostic/seed").status_code in (401, 403)


def test_pregunta_inexistente_en_el_envio_es_rechazada(client, estudiante, diagnostico_28):
    attempt_id = iniciar(client, estudiante).json()["attempt_id"]
    r = enviar(client, estudiante, attempt_id, [(99999, RESPUESTA_OK)])
    assert r.status_code in (400, 422)
