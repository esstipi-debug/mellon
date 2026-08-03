"""Las fronteras de los dos roles de la cosecha.

Un rol que puede violar su prohibicion no tiene prohibicion, tiene una
sugerencia. Por eso la frontera del testigo NO se decide con lo que el agente
declara: `cosecha.cosechar` la evalua sobre la union de esa declaracion y los
archivos que el episodio trae del diff de git, y alcanza con que una sola de
las dos fuentes muestre un archivo de mas para descartar el episodio.

La frontera del reparador no la verifica nadie todavia, porque no hay
reparador: `FRONTERAS["reparador"]` existe como dato y esta sin usar.

La frontera es una lista de prefijos PERMITIDOS, no de prohibidos. Prohibir la
carpeta del otro rol dejaria abierto todo lo demas -- pyproject, docs, tools --
y el harness no tiene nada que hacer ahi.

Las rutas se normalizan antes de comparar el prefijo, y sin tocar el disco:
`tests/../src/x.py` empieza con `tests/` y no es un archivo de tests. No se usa
`Path.resolve()` a proposito -- consulta el filesystem y sigue symlinks, asi que
el veredicto dependeria de que el arbol este montado, que es justo lo que la
cosecha no puede asumir.
"""

from __future__ import annotations

import posixpath
from typing import Iterable

FRONTERAS: dict[str, tuple[str, ...]] = {
    "testigo": ("tests/",),
    "reparador": ("src/",),
}


def _normalizada(archivo: str) -> str:
    """Colapsa `.`, `..` y separadores sin consultar el disco.

    Las barras invertidas se pasan a `/` primero: en Windows `a\\..\\b` es la
    misma ruta que `a/../b`, y comparar prefijos sobre la forma cruda dejaria
    pasar una de las dos.
    """
    return posixpath.normpath(archivo.replace("\\", "/"))


def _escapa_del_arbol(normalizada: str) -> bool:
    """True si la ruta sale del arbol o es absoluta: nunca esta permitida."""
    return normalizada == ".." or normalizada.startswith("../") or posixpath.isabs(normalizada)


def viola_frontera(rol: str, archivos: Iterable[str]) -> list[str]:
    """Devuelve los archivos que el rol no tenia permitido tocar.

    Devuelve la ruta TAL COMO llego, no la normalizada: quien lee el descarte
    necesita ver lo que se declaro, no lo que el chequeo dedujo.
    """
    if rol not in FRONTERAS:
        raise ValueError(f"rol desconocido: {rol}. Opciones: {', '.join(FRONTERAS)}")
    permitidos = FRONTERAS[rol]
    invadidos: list[str] = []
    for a in archivos:
        normal = _normalizada(a)
        if _escapa_del_arbol(normal) or not normal.startswith(permitidos):
            invadidos.append(a)
    return invadidos
