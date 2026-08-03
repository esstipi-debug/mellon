"""Un guardia es un predicado con su motivo escrito al lado.

El modelo es ARCHIVOS_CON_ACENTOS_A_PROPOSITO en tests/test_convenciones.py:
cada excepcion trae el porque, y por eso seis meses despues se puede decidir
si sigue valiendo. Un guardia sin motivo es el que nadie sabe si puede borrar,
y el que termina borrado el dia que molesta.

`evaluar` devuelve Hallazgos y no booleanos porque un booleano pierde la
procedencia: lo que sale de un guardia violado tiene que rastrearse hasta el
commit que lo origino.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from .hallazgo import Hallazgo


@dataclass(frozen=True)
class Guardia:
    """`predicado` devuelve True cuando el objeto esta SANO."""

    nombre: str
    motivo: str
    hallazgo: Hallazgo
    predicado: Callable[[object], bool]

    def __post_init__(self) -> None:
        if not self.nombre:
            raise ValueError("guardia sin nombre")
        if not self.motivo:
            raise ValueError("guardia sin motivo: es el que nadie sabe si puede borrar")


def evaluar(guardias: Iterable[Guardia], obj: object) -> list[Hallazgo]:
    """Corre todos los guardias y devuelve los Hallazgos de los violados.

    Un guardia que revienta se reporta como violado en vez de tumbar la
    evaluacion. Es la misma degradacion por unidad que hace el store al leer:
    un archivo ilegible no puede apagar toda la fase 4.
    """
    fallas: list[Hallazgo] = []
    for g in guardias:
        try:
            sano = g.predicado(obj)
        except Exception as exc:  # noqa: BLE001 -- un guardia roto no apaga a los demas
            fallas.append(
                Hallazgo(
                    regla=g.hallazgo.regla,
                    evidencia=f"el guardia {g.nombre} reviento al evaluar: {exc!r}",
                    procedencia=g.hallazgo.procedencia,
                    familia=g.hallazgo.familia,
                )
            )
            continue
        if not sano:
            fallas.append(g.hallazgo)
    return fallas
