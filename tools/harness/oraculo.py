"""El veredicto: dos arboles, la suite completa, ninguna afirmacion.

Un test verde no prueba nada cuando el mismo proceso escribio el test y el
arreglo: prueba que los dos comparten el error. Lo que si prueba algo es correr
el test contra el arbol donde el bug TODAVIA EXISTE. Si ahi pasa, el test es
vacuo y el episodio se voltea entero.

Y no alcanza con el test nuevo: la suite completa corre en los dos arboles,
porque el modo de falla de este repo es el numero plausible, y un arreglo que
cura un numero y rompe otro se ve solo mirando los demas.

La semantica de regresion es 'no empeorar', la misma que save() en el store: un
test que ya fallaba antes sigue fallando y no es culpa de este episodio.

`correr` se recibe como argumento a proposito: el oraculo es una decision, no
un ejecutor. Quien lo llama decide si corre pytest de verdad o simula.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Veredicto:
    acepta: bool
    motivo: str
    fallo_en_antes: bool
    paso_en_despues: bool
    regresiones: tuple[str, ...]


def veredicto(
    test_nuevo: str,
    correr: Callable[[str], set[str]],
    commit_antes: str,
    commit_despues: str,
) -> Veredicto:
    """Acepta el episodio solo si el test nuevo fallaba antes, pasa ahora, y
    ningun test que pasaba antes empeoro."""
    fallan_antes = set(correr(commit_antes))
    fallan_despues = set(correr(commit_despues))

    fallo_en_antes = test_nuevo in fallan_antes
    paso_en_despues = test_nuevo not in fallan_despues
    regresiones = tuple(sorted(fallan_despues - fallan_antes))

    if not fallo_en_antes:
        motivo = (
            f"test vacuo: {test_nuevo} pasa en {commit_antes}, donde el bug todavia existe. "
            "Un test que no distingue el arbol roto del arreglado no prueba nada."
        )
        return Veredicto(False, motivo, fallo_en_antes, paso_en_despues, regresiones)

    if not paso_en_despues:
        motivo = f"el test {test_nuevo} sigue fallando en {commit_despues}: el arreglo no lo cura"
        return Veredicto(False, motivo, fallo_en_antes, paso_en_despues, regresiones)

    if regresiones:
        motivo = (
            f"regresiones en {commit_despues}: {', '.join(regresiones)}. "
            "El test nuevo esta verde pero la suite empeoro."
        )
        return Veredicto(False, motivo, fallo_en_antes, paso_en_despues, regresiones)

    return Veredicto(True, "", fallo_en_antes, paso_en_despues, ())
