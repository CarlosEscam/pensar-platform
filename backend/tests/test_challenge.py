"""Pruebas unitarias de calificación (FPI-14, RN-02) con Stub y estrategias (FPI-11)."""
from app.models.challenge import ChallengeType
from app.services.graders import (
    ClosedChallengeGrader,
    SemiStructuredChallengeGrader,
    get_grader,
)


class ChallengeStub:
    """Stub: devuelve datos fijos; no registra cómo se le llama."""

    def __init__(self, valid_structures=None, correct_answer=None):
        self.valid_structures = valid_structures
        self.correct_answer = correct_answer

    def matches_structure(self, submitted_answer):
        return submitted_answer in (self.valid_structures or [])


def test_matches_structure_ignores_key_order():
    stub = ChallengeStub(valid_structures=[{"a": [1, 2], "b": [3]}, {"x": [1], "y": [2, 3]}])
    respuesta_reordenada = {"b": [3], "a": [1, 2]}
    assert stub.matches_structure(respuesta_reordenada) is True


def test_semi_structured_grader_acepta_y_rechaza():
    stub = ChallengeStub(valid_structures=[{"g1": [1], "g2": [2]}])
    grader = SemiStructuredChallengeGrader()
    assert grader.grade({"g2": [2], "g1": [1]}, stub) is True
    assert grader.grade({"g1": [2], "g2": [1]}, stub) is False


def test_closed_grader_camino_feliz_y_respuesta_incorrecta():
    stub = ChallengeStub(correct_answer={"orden": [2, 1, 3]})
    grader = ClosedChallengeGrader()
    assert grader.grade({"orden": [2, 1, 3]}, stub) is True
    assert grader.grade({"orden": [1, 2, 3]}, stub) is False


def test_get_grader_selecciona_la_estrategia_por_tipo():
    assert isinstance(get_grader(ChallengeType.CLOSED), ClosedChallengeGrader)
    assert isinstance(get_grader(ChallengeType.SEMI_STRUCTURED), SemiStructuredChallengeGrader)
    assert get_grader(ChallengeType.BLOCKS) is None
