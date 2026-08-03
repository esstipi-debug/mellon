"""El episodio: el par de arboles que el oraculo necesita para dar veredicto.

Un episodio se cierra cuando una corrida deja en verde tests que la corrida
anterior tenia en rojo. El par (commit_antes, commit_despues) es lo unico que
hace falta para reconstruir los dos arboles.

El log es append-only. Un episodio que no dio leccion se MARCA, no se borra --
pero marcar es responsabilidad del LLAMADOR, no de la cosecha. `cosechar`
recibe un iterable de episodios y no sabe de que archivo salieron; devuelve en
`Resultado.marcas` los pares (indice, estado_nuevo) para que quien leyo el log
con `leer` cierre el circulo llamando a `marcar`. Si nadie llama a `marcar`, el
log queda en `abierto` y la proxima cosecha reprocesa todo: eso es una falla del
llamador, no una promesa rota de este modulo.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

ESTADOS = ("abierto", "irreproducible", "descartado", "destilado")
"""abierto: sin procesar. irreproducible: el arbol estaba sucio y no hay HEAD
que lo reproduzca. descartado: la cosecha lo miro y no dio leccion.
destilado: produjo un guardia."""


@dataclass(frozen=True)
class Episodio:
    fecha: str
    commit_antes: str
    commit_despues: str
    tests_que_fallaban: tuple[str, ...]
    archivos_tocados: tuple[str, ...]
    """El diff del COMMIT DE ARREGLO HISTORICO, tal como lo entrega
    `git log --name-only`. Toca `src/` POR CONSTRUCCION: la definicion de
    episodio en `historia.py` es un commit que toca `src/` Y `tests/` a la vez.

    Por eso NUNCA se pasa por la frontera del testigo. Son dos diffs distintos:
    este es el arreglo que un humano ya hizo en el pasado, y la frontera del
    testigo describe lo que el agente testigo escribe durante una cosecha.
    Confundirlos hace que ningun episodio real produzca guardia jamas -- ya paso
    una vez, y el fixture de los tests tuvo que volverse irreal para taparlo."""
    mensaje: str
    estado: str = "abierto"


def _a_episodio(fila: dict) -> Episodio:
    return Episodio(
        fecha=fila["fecha"],
        commit_antes=fila["commit_antes"],
        commit_despues=fila["commit_despues"],
        tests_que_fallaban=tuple(fila.get("tests_que_fallaban", ())),
        archivos_tocados=tuple(fila.get("archivos_tocados", ())),
        mensaje=fila.get("mensaje", ""),
        estado=fila.get("estado", "abierto"),
    )


def leer(path: Path) -> list[Episodio]:
    """Lee el log. Una linea ilegible se saltea sin tumbar las demas."""
    p = Path(path)
    if not p.exists():
        return []
    eps: list[Episodio] = []
    for linea in p.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        try:
            eps.append(_a_episodio(json.loads(linea)))
        except (ValueError, KeyError):
            continue
    return eps


def agregar(path: Path, ep: Episodio) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(ep), ensure_ascii=False) + "\n")


def marcar(path: Path, indice: int, estado: str) -> None:
    """Cambia el estado de un episodio reescribiendo el archivo entero.

    Reescribe en vez de agregar porque el estado es del episodio, no un evento
    nuevo. Las filas ilegibles se pierden en la reescritura y eso es aceptable:
    ya eran ilegibles.
    """
    if estado not in ESTADOS:
        raise ValueError(f"estado desconocido: {estado}. Opciones: {', '.join(ESTADOS)}")
    eps = leer(path)
    eps[indice] = replace(eps[indice], estado=estado)
    p = Path(path)
    p.write_text(
        "".join(json.dumps(asdict(e), ensure_ascii=False) + "\n" for e in eps),
        encoding="utf-8",
    )
