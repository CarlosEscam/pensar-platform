"""Pruebas unitarias del dominio de gamificación (FPI-14, RN-03). Función pura: sin dobles."""
from app.core.config import POINTS_PER_LEVEL
from app.models.challenge import StudentProfile


def _perfil(puntos: int) -> StudentProfile:
    return StudentProfile(total_points=puntos, current_level=1)


def test_recalculate_level_at_50_points():
    profile = _perfil(55)
    profile.recalculate_level()
    assert profile.current_level == (55 // 50) + 1 == 2


def test_recalculate_level_fronteras():
    for puntos, nivel in [(0, 1), (49, 1), (50, 2), (99, 2), (100, 3)]:
        profile = _perfil(puntos)
        profile.recalculate_level()
        assert profile.current_level == nivel


def test_recalculate_level_usa_la_constante_de_config():
    profile = _perfil(POINTS_PER_LEVEL * 3)
    profile.recalculate_level()
    assert profile.current_level == 4
