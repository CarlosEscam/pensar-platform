"""Caminos 3 y 4 del análisis de V(G) de submit_challenge_attempt (FPI-14)."""
from app.models import Challenge, ChallengeType, DifficultyLevel

from tests.conftest import crear_reto_semi


def test_tipo_de_reto_no_soportado_devuelve_400_camino_3(client, db, dimensiones, estudiante):
    reto = Challenge(
        title="Reto de bloques",
        description="Programación visual (futuro)",
        dimension_id=dimensiones["algorithms"],
        difficulty=DifficultyLevel.ADVANCED,
        challenge_type=ChallengeType.BLOCKS,
        content={"text": "Arma el programa"},
        points_reward=20,
    )
    db.add(reto)
    db.commit()
    r = client.post(
        f"/challenges/{reto.id}/attempt", json={"submitted_answer": {"x": 1}}, headers=estudiante
    )
    assert r.status_code == 400


def test_reto_semi_sin_estructuras_validas_devuelve_500_camino_4(
    client, db, dimensiones, estudiante
):
    reto_id = crear_reto_semi(db, dimensiones["abstraction"], estructuras=[])
    r = client.post(
        f"/challenges/{reto_id}/attempt", json={"submitted_answer": {"x": 1}}, headers=estudiante
    )
    assert r.status_code == 500
