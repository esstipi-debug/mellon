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

from dataclasses import dataclass, field

BUGS_HISTORICOS = 17
"""Los bugs de clase 'no falla, miente' documentados en HANDOFF.md. Es el
denominador del unico puntaje que hace falsable al harness."""


@dataclass(frozen=True)
class CoberturaGuardia:
    familias_vigiladas: tuple[str, ...] = ()
    bugs_historicos: int = BUGS_HISTORICOS
    bugs_atrapados: int = 0

    @property
    def is_complete(self) -> bool:
        return False  # nunca, y por eso se muestra

    def nota(self) -> str:
        cuales = ", ".join(self.familias_vigiladas) if self.familias_vigiladas else "ninguna familia todavia"
        return (
            "Este harness no vigila el bug que nunca fallo: sin un test en rojo no hay "
            "episodio que capturar, y ese es el patron dominante del repo.\n"
            f"Vigila {cuales}.\n"
            f"Contra los bugs historicos atrapa {self.bugs_atrapados} de {self.bugs_historicos}."
        )
