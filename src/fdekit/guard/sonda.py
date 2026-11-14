"""Sonda de dos corridas para un Guardia.

Un guardia que solo se corrio sobre datos sanos no prueba nada: el que aprueba
todo -- el oraculo vacuo -- da el mismo resultado que el que funciona. La sonda
lo corre dos veces, sobre el objeto sano y sobre el mismo objeto con el defecto
inyectado, y recien con las dos corridas dice que detecta.

Es `sonda_dos_corridas` de Kern (src/bateria/barrido_neteo.py) llevada a los
guardias, con su misma regla: cuando no hubo nada que medir, el resultado es
SIN_MEDIR y no un veredicto contra el guardia. "No encontre" y "no podia
encontrar" son resultados distintos, y colapsarlos es la mentira que la regla 3
prohibe.

Stdlib pura (regla 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .guardia import Guardia, evaluar
from .hallazgo import Hallazgo


class Veredicto(str, Enum):
    DETECTA = "detecta"
    VACUO = "vacuo"
    """Pasa sobre el sano y sobre el mutado: no mira el defecto."""
    FALSO_POSITIVO = "falso_positivo"
    """Salta sobre el objeto sano."""
    REVIENTA = "revienta"
    """Tiro una excepcion en alguna corrida: no evaluo, aunque `evaluar` lo
    reporte como violado para no apagar a los demas guardias."""
    SIN_MEDIR = "sin_medir"
    """El mutado es igual al sano: no hubo defecto que detectar."""


@dataclass(frozen=True)
class ResultadoSonda:
    guardia: str
    familia: str
    veredicto: Veredicto
    evidencia: str


def _evidencias(hallazgos: list[Hallazgo]) -> str:
    return "; ".join(h.evidencia for h in hallazgos)


def _iguales(a: object, b: object) -> bool:
    """La igualdad la decide `==`. Un objeto que no compara por valor, o cuya
    comparacion revienta o no devuelve un booleano, cuenta como distinto: la
    sonda sigue y el veredicto sale de las dos corridas."""
    try:
        return (a == b) is True
    except Exception:  # noqa: BLE001 -- comparar no puede tumbar la sonda
        return False


def sonda_guardia(
    guardia: Guardia,
    fabrica_sano: Callable[[], object],
    fabrica_mutado: Callable[[], object],
) -> ResultadoSonda:
    """Corre `guardia` sobre el objeto sano y sobre el mutado, y clasifica.

    Recibe fabricas y no objetos: cada corrida evalua un objeto recien hecho, asi
    que un guardia que modifica lo que mira no contamina la otra corrida.

    DETECTA exige que el mutado devuelva exactamente `[guardia.hallazgo]`, con su
    procedencia: un hallazgo armado por `evaluar` porque el predicado reviento
    tiene otra evidencia, y cuenta como REVIENTA.
    """
    sano, mutado = fabrica_sano(), fabrica_mutado()

    def resultado(veredicto: Veredicto, evidencia: str) -> ResultadoSonda:
        return ResultadoSonda(guardia.nombre, guardia.hallazgo.familia, veredicto, evidencia)

    if _iguales(sano, mutado):
        return resultado(Veredicto.SIN_MEDIR, (
            "el objeto mutado es igual al sano: no hubo defecto que detectar, "
            "asi que no se acredita ni se niega"
        ))

    sobre_sano = evaluar([guardia], sano)
    if sobre_sano == [guardia.hallazgo]:
        return resultado(Veredicto.FALSO_POSITIVO,
                         f"salta sobre el objeto sano: {guardia.hallazgo.regla}")
    if sobre_sano:
        return resultado(Veredicto.REVIENTA, f"sobre el sano: {_evidencias(sobre_sano)}")

    sobre_mutado = evaluar([guardia], mutado)
    if not sobre_mutado:
        return resultado(Veredicto.VACUO,
                         "pasa sobre el sano y sobre el mutado: no mira el defecto")
    if sobre_mutado == [guardia.hallazgo]:
        p = guardia.hallazgo.procedencia
        return resultado(Veredicto.DETECTA, (
            f"sano -> 0 hallazgos; mutado -> '{guardia.hallazgo.regla}' "
            f"(procedencia {p.commit}, {p.fecha.isoformat()}, {p.dueno})"
        ))
    return resultado(Veredicto.REVIENTA, f"sobre el mutado: {_evidencias(sobre_mutado)}")
