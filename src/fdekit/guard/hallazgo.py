"""El dato que cruza las dos capas del harness.

Un Hallazgo es una afirmacion sobre el repo o sobre los datos. La procedencia
es obligatoria en el constructor y no por prolijidad: la memoria en prosa de
este proyecto ya mintio una vez -- el HANDOFF confiesa que sus hashes
posteriores a 17b6901 no sirven, y que los viejos siguen existiendo como
objetos huerfanos, asi que `git show` sobre ellos funciona y engana. Un tipo
que se puede construir sin commit reproduce esa falla en cada instancia.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Procedencia:
    """De donde salio la afirmacion. Los tres campos son obligatorios."""

    commit: str
    fecha: date
    dueno: str

    def __post_init__(self) -> None:
        if not self.commit:
            raise ValueError("procedencia sin commit: una afirmacion sobre el repo sin hash que la ancle no es verificable")
        if not self.dueno:
            raise ValueError("procedencia sin dueno: la regla 1 del repo pide dueno para todo lo que va a una cola")


@dataclass(frozen=True)
class Hallazgo:
    """Una afirmacion con su evidencia y su procedencia.

    `familia` agrupa hallazgos del mismo tipo de error. Vacia significa sin
    clasificar, nunca "ninguna" -- es ausencia de dato, no evidencia.
    """

    regla: str
    evidencia: str
    procedencia: Procedencia
    familia: str = ""

    def __post_init__(self) -> None:
        if not self.regla:
            raise ValueError("hallazgo sin regla: no dice que es lo que no se puede volver a hacer")
