"""Genera el indice legible del corpus de guardias.

El corpus ejecutable es la memoria; esto es solo una vista. Se arma parseando
el texto de cada guardia con ast en vez de importarlo: un guardia con un
SyntaxError, o uno que hace algo al importarse, no puede apagar la generacion
del indice de todos los demas.
"""

from __future__ import annotations

import ast
from pathlib import Path

ENCABEZADO = (
    "# Lecciones del harness\n\n"
    "> Archivo GENERADO por `tools/harness/indice.py` desde `tests/guards/`.\n"
    "> No editar a mano: la proxima regeneracion se come los cambios.\n"
    "> La memoria real son los tests; esto es una vista.\n\n"
)


def _leccion(texto: str) -> dict | None:
    """Extrae el dict LECCION de nivel de modulo, sin importar el modulo."""
    try:
        arbol = ast.parse(texto)
    except SyntaxError:
        return None
    for nodo in arbol.body:
        if not isinstance(nodo, ast.Assign):
            continue
        for destino in nodo.targets:
            if isinstance(destino, ast.Name) and destino.id == "LECCION":
                try:
                    valor = ast.literal_eval(nodo.value)
                except ValueError:
                    return None
                return valor if isinstance(valor, dict) else None
    return None


def indice(guards_dir: Path) -> str:
    d = Path(guards_dir)
    archivos = sorted(p for p in d.glob("*") if p.is_file() and p.name != "__init__.py")
    if not archivos:
        return ENCABEZADO + "todavia no hay guardias en el corpus.\n"

    filas = ["| guardia | familia | regla | commit | fecha | dueno |", "|---|---|---|---|---|---|"]
    for p in archivos:
        lec = _leccion(p.read_text(encoding="utf-8"))
        if lec is None:
            filas.append(f"| `{p.stem}` | - | **sin procedencia** - no declara `LECCION` | - | - | - |")
            continue
        filas.append(
            f"| `{p.stem}` | {lec.get('familia', '-')} | {lec.get('regla', '-')} | "
            f"`{lec.get('commit', '-')}` | {lec.get('fecha', '-')} | {lec.get('dueno', '-')} |"
        )
    return ENCABEZADO + "\n".join(filas) + "\n"
