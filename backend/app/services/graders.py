"""Calificación de retos mediante el patrón Strategy (diseño de la FPI-11).

Cada tipo de reto tiene su propia estrategia; agregar un tipo nuevo (p. ej. bloques)
no exige modificar las existentes (principio abierto/cerrado).
"""
from typing import Protocol

from ..models.challenge import Challenge, ChallengeType


class ChallengeGrader(Protocol):
    def grade(self, submitted_answer: dict, challenge: Challenge) -> bool: ...


class ClosedChallengeGrader:
    """Reto cerrado: la respuesta debe ser exactamente la correcta."""

    def grade(self, submitted_answer: dict, challenge: Challenge) -> bool:
        return submitted_answer == challenge.correct_answer


class SemiStructuredChallengeGrader:
    """RN-02: correcto si coincide con ALGUNA de las estructuras válidas.

    La comparación de diccionarios no depende del orden de las claves.
    """

    def grade(self, submitted_answer: dict, challenge: Challenge) -> bool:
        return challenge.matches_structure(submitted_answer)


_GRADERS: dict[ChallengeType, ChallengeGrader] = {
    ChallengeType.CLOSED: ClosedChallengeGrader(),
    ChallengeType.SEMI_STRUCTURED: SemiStructuredChallengeGrader(),
}


def get_grader(challenge_type: ChallengeType) -> ChallengeGrader | None:
    return _GRADERS.get(challenge_type)
