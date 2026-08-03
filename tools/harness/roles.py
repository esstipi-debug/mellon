"""Las fronteras de los dos roles de la cosecha, verificadas sobre el diff.

Un rol que puede violar su prohibicion no tiene prohibicion, tiene una
sugerencia. Por eso esto no se le pide al agente: se calcula sobre los archivos
que efectivamente toco.

La frontera es una lista de prefijos PERMITIDOS, no de prohibidos. Prohibir la
carpeta del otro rol dejaria abierto todo lo demas -- pyproject, docs, tools --
y el harness no tiene nada que hacer ahi.
"""

from __future__ import annotations

from typing import Iterable

FRONTERAS: dict[str, tuple[str, ...]] = {
    "testigo": ("tests/",),
    "reparador": ("src/",),
}


def viola_frontera(rol: str, archivos: Iterable[str]) -> list[str]:
    """Devuelve los archivos que el rol no tenia permitido tocar."""
    if rol not in FRONTERAS:
        raise ValueError(f"rol desconocido: {rol}. Opciones: {', '.join(FRONTERAS)}")
    permitidos = FRONTERAS[rol]
    return [a for a in archivos if not a.startswith(permitidos)]
