"""La mitad del harness que corre sola, y por eso solo observa.

La frontera del diseno: capturar nunca miente, actuar si puede. Este modulo no
escribe codigo, no interpreta y no clasifica. Escribe un renglon cuando una
corrida deja en verde tests que la anterior tenia en rojo.

Es una funcion pura sobre el estado en disco: recibe el resultado de la corrida
como argumento en vez de correr pytest adentro. Eso la vuelve testeable sin
subprocess y sin git, que es la unica forma de que el hook sea confiable.

Si algo sale mal, devuelve None. Un hook que revienta molesta en cada corrida y
termina desactivado; perder un episodio no cuesta nada.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .episodio import Episodio


def _ultima(path: Path) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return None


def registrar_corrida(
    estado_path: Path,
    head: str,
    fallidos: Iterable[str],
    archivos_tocados: Iterable[str],
    mensaje: str,
    today: str,
    arbol_limpio: bool = True,
) -> Episodio | None:
    """Guarda esta corrida y devuelve un Episodio si cerro uno.

    `today` es argumento y no `date.today()`: regla 4 del repo.
    """
    fallidos = tuple(fallidos)
    previa = _ultima(estado_path)

    ep: Episodio | None = None
    if previa is not None:
        curados = tuple(t for t in previa.get("fallidos", ()) if t not in fallidos)
        if curados:
            ep = Episodio(
                fecha=today,
                commit_antes=previa.get("head", ""),
                commit_despues=head,
                tests_que_fallaban=curados,
                archivos_tocados=tuple(archivos_tocados),
                mensaje=mensaje,
                estado="abierto" if previa.get("arbol_limpio", True) else "irreproducible",
            )

    p = Path(estado_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"head": head, "fallidos": list(fallidos), "arbol_limpio": arbol_limpio}, ensure_ascii=False),
        encoding="utf-8",
    )
    return ep
