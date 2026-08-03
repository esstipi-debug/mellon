"""La honestidad del harness, con el mismo contrato que Coverage.

`Coverage` (decide/query.py) existe porque Serena puede prometer que
find_referencing_symbols devuelve todo -- tiene un compilador abajo -- y
nosotros no. Un harness de self-healing hereda exactamente la misma clase de
promesa: "detecta los bugs". No los detecta todos y nunca va a poder.

El limite concreto de este harness no es un detalle de implementacion, es una
consecuencia del oraculo que se eligio: sin invariantes externas al test, solo
aprende de fracasos que YA se manifestaron como test rojo. El bug que no falla
-- que es el patron dominante de este repo, 17 casos documentados -- no genera
episodio. Por eso `nota()` lo dice en la PRIMERA linea y no en una nota al pie.
"""

from __future__ import annotations

from dataclasses import dataclass

BUGS_HISTORICOS = 17
"""Los bugs de clase 'no falla, miente' documentados en HANDOFF.md. Es el
denominador del unico puntaje que hace falsable al harness."""


@dataclass(frozen=True)
class CoberturaGuardia:
    familias_vigiladas: tuple[str, ...] = ()
    bugs_historicos: int = BUGS_HISTORICOS
    bugs_atrapados: int | None = None
    """Cuantos de los `bugs_historicos` atrapo un guardia. None significa SIN
    MEDIR, y es el default a proposito: nada en el sistema mapea un episodio a
    uno de los 17 casos de HANDOFF.md, asi que un cero por defecto seria un dato
    inventado. Cero es un resultado -- medimos y no atrapamos ninguno -- y
    ausencia de dato no es un resultado. Lo puebla quien haya hecho la medicion,
    no la cosecha."""

    @property
    def is_complete(self) -> bool:
        return False  # nunca, y por eso se muestra

    def nota(self) -> str:
        cuales = ", ".join(self.familias_vigiladas) if self.familias_vigiladas else "ninguna familia todavia"
        if self.bugs_atrapados is None:
            puntaje = (
                f"Contra los {self.bugs_historicos} bugs historicos: SIN MEDIR. "
                "Nadie corrio la falsificacion, asi que no hay numerador -- no es cero."
            )
        else:
            puntaje = f"Contra los bugs historicos atrapa {self.bugs_atrapados} de {self.bugs_historicos}."
        return (
            "Este harness no vigila el bug que nunca fallo: sin un test en rojo no hay "
            "episodio que capturar, y ese es el patron dominante del repo.\n"
            f"Vigila {cuales}.\n"
            f"{puntaje}"
        )
